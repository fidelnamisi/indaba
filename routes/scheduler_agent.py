"""
Indaba Scheduler — ENFORCED META-SCHEDULE v2

14-day rolling window, deterministic slot assignment.

Fixed daily slots (SAST = UTC+2):
  Mon–Sat  07:30  PROVERB
  Mon–Sat  12:15  NOVEL_SERIAL
  Mon–Sat  18:30  FLASH_FICTION
  Sunday   09:00  PROVERB

Content queues (FIFO):
  PROVERB       — promo_proverbs.json where queue_status is None AND composite_path set
  NOVEL_SERIAL  — works.json, profile num_chunks is None, chunks without vip/message_id
  FLASH_FICTION — works.json, profile num_chunks is not None, chunks with status 'pending'

Novel: dual delivery — VIP at slot time, Channel = VIP + 24h.
Flash: single channel delivery.
"""

import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from utils.json_store import read_json, write_json
from utils.constants import (
    PROMO_WORKS_FILE, PROMO_MESSAGES_FILE,
    PROMO_PROVERBS_FILE, PROMO_SETTINGS_FILE,
)
from services.distribution_service import push_to_outbox

bp = Blueprint('scheduler_agent', __name__)

SAST = timezone(timedelta(hours=2))
WINDOW_DAYS = 14
SLOT_TOLERANCE_MINUTES = 20  # ±20 min to detect an occupied slot


# ── Slot definitions ───────────────────────────────────────────────────────────

# weekdays: 0=Mon … 5=Sat, 6=Sun
_SLOT_DEFS = [
    {'days': [0, 1, 2, 3, 4, 5], 'hour': 7,  'minute': 30, 'type': 'PROVERB'},
    {'days': [0, 1, 2, 3, 4, 5], 'hour': 12, 'minute': 15, 'type': 'NOVEL_SERIAL'},
    {'days': [0, 1, 2, 3, 4, 5], 'hour': 18, 'minute': 30, 'type': 'FLASH_FICTION'},
    {'days': [6],                 'hour': 9,  'minute': 0,  'type': 'PROVERB'},
]


def _build_calendar():
    """Return list of {'dt': datetime_sast, 'type': str} for next WINDOW_DAYS days."""
    today = datetime.now(SAST).date()
    slots = []
    for day_offset in range(WINDOW_DAYS):
        d = today + timedelta(days=day_offset)
        for defn in _SLOT_DEFS:
            if d.weekday() in defn['days']:
                dt = datetime(d.year, d.month, d.day,
                              defn['hour'], defn['minute'], 0, tzinfo=SAST)
                slots.append({'dt': dt, 'type': defn['type']})
    slots.sort(key=lambda s: s['dt'])
    return slots


def _occupied_datetimes(messages):
    """Return list of SAST datetimes for already-queued messages."""
    result = []
    for msg in messages:
        if msg.get('status') != 'queued':
            continue
        sat = msg.get('scheduled_at')
        if not sat:
            continue
        try:
            dt = datetime.fromisoformat(sat.replace('Z', '+00:00'))
            result.append(dt.astimezone(SAST))
        except (ValueError, AttributeError):
            pass
    return result


def _is_occupied(slot_dt, occupied, tol=SLOT_TOLERANCE_MINUTES):
    tol_secs = tol * 60
    for odt in occupied:
        if abs((slot_dt - odt).total_seconds()) <= tol_secs:
            return True
    return False


def _build_queues(settings):
    """Return (proverb_queue, novel_queue, flash_queue) as FIFO lists."""
    profiles = settings.get('serializer_profiles', [])

    # Proverbs ready to post: queue_status is None + composite_path exists
    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {'proverbs': []}
    proverb_queue = [
        p for p in proverbs_data.get('proverbs', [])
        if p.get('queue_status') is None and p.get('composite_path')
    ]

    # Works
    works_data = read_json(PROMO_WORKS_FILE) or {'works': []}
    novel_queue = []
    flash_queue = []

    for work in works_data.get('works', []):
        profile_id = work.get('profile_id', '')
        profile = next((p for p in profiles if p['id'] == profile_id), None)
        if profile is None:
            continue

        is_novel = profile.get('num_chunks') is None

        for chunk in work.get('chunks', []):
            if is_novel:
                # Unqueued novel chunk: no vip_message_id and no legacy message_id
                if not chunk.get('vip_message_id') and not chunk.get('message_id'):
                    novel_queue.append({'work': work, 'chunk': chunk})
            else:
                # Unqueued flash/short chunk: status pending and no message_id
                if chunk.get('status') == 'pending' and not chunk.get('message_id'):
                    flash_queue.append({'work': work, 'chunk': chunk})

    return proverb_queue, novel_queue, flash_queue, proverbs_data, works_data


def _run(dry_run=False):
    settings = read_json(PROMO_SETTINGS_FILE) or {}
    wa = settings.get('publishing_wa_recipients', {})

    vip_group_id    = wa.get('vip_group_id', '').strip()
    vip_group_label = wa.get('vip_group_label', 'Realms & Roads VIP Group')
    channel_id      = (wa.get('channel_id') or '').strip() or os.environ.get('GOWA_CHANNEL_ID', '')
    channel_label   = wa.get('channel_label', 'WA Channel')

    all_messages = (read_json(PROMO_MESSAGES_FILE) or {'messages': []}).get('messages', [])
    occupied     = _occupied_datetimes(all_messages)

    proverb_queue, novel_queue, flash_queue, proverbs_data, works_data = _build_queues(settings)

    calendar = _build_calendar()
    now      = datetime.now(SAST)
    actions  = []

    for slot in calendar:
        if slot['dt'] <= now:
            continue
        if _is_occupied(slot['dt'], occupied):
            continue

        slot_type = slot['type']
        slot_iso  = slot['dt'].replace(microsecond=0).isoformat()

        # ── PROVERB ────────────────────────────────────────────────────────────
        if slot_type == 'PROVERB' and proverb_queue:
            proverb = proverb_queue.pop(0)
            action = {
                'slot': slot_iso,
                'type': 'PROVERB',
                'proverb_id': proverb['id'],
                'text': proverb['text'][:80],
            }
            if not dry_run:
                result = push_to_outbox(
                    recipient_phone=channel_id,
                    recipient_name=channel_label,
                    content=proverb['text'],
                    source='wa_post_maker',
                    media_url=proverb.get('composite_path'),
                    proverb_id=proverb['id'],
                    scheduled_at=slot_iso,
                )
                proverb['queue_status'] = 'approved'
                from datetime import datetime as _dt
                proverb['updated_at'] = _dt.utcnow().isoformat() + 'Z'
                action['message_id'] = result['id']
                occupied.append(slot['dt'])
            actions.append(action)

        # ── NOVEL_SERIAL ───────────────────────────────────────────────────────
        elif slot_type == 'NOVEL_SERIAL' and novel_queue:
            item  = novel_queue.pop(0)
            work  = item['work']
            chunk = item['chunk']

            content = chunk['content']
            post_header = work.get('post_header', '').strip()
            if post_header:
                content = f"{post_header}\n\n{content}"

            channel_dt  = slot['dt'] + timedelta(hours=24)
            channel_iso = channel_dt.replace(microsecond=0).isoformat()

            action = {
                'slot': slot_iso,
                'type': 'NOVEL_SERIAL',
                'work_id': work['id'],
                'chunk_id': chunk['id'],
                'title': chunk['content'][:60].split('\n')[0],
                'vip_scheduled_at': slot_iso,
                'channel_scheduled_at': channel_iso,
            }

            if not dry_run:
                src_ref = {'work_id': work['id'], 'module_id': chunk['id']}
                vip_res = push_to_outbox(
                    recipient_phone=vip_group_id,
                    recipient_name=vip_group_label,
                    content=content,
                    source='work_serializer',
                    scheduled_at=slot_iso,
                    source_ref=src_ref,
                )
                ch_res = push_to_outbox(
                    recipient_phone=channel_id,
                    recipient_name=channel_label,
                    content=content,
                    source='work_serializer',
                    scheduled_at=channel_iso,
                    source_ref=src_ref,
                )
                chunk['status']               = 'queued'
                chunk['vip_message_id']       = vip_res['id']
                chunk['vip_scheduled_at']     = slot_iso
                chunk['channel_message_id']   = ch_res['id']
                chunk['channel_scheduled_at'] = channel_iso
                chunk.pop('message_id', None)

                action['vip_message_id']     = vip_res['id']
                action['channel_message_id'] = ch_res['id']
                occupied.append(slot['dt'])
                occupied.append(channel_dt)

            actions.append(action)

        # ── FLASH_FICTION ──────────────────────────────────────────────────────
        elif slot_type == 'FLASH_FICTION' and flash_queue:
            item  = flash_queue.pop(0)
            work  = item['work']
            chunk = item['chunk']

            content = chunk['content']
            post_header = work.get('post_header', '').strip()
            if post_header:
                content = f"{post_header}\n\n{content}"

            action = {
                'slot': slot_iso,
                'type': 'FLASH_FICTION',
                'work_id': work['id'],
                'chunk_id': chunk['id'],
                'title': chunk['content'][:60].split('\n')[0],
            }

            if not dry_run:
                src_ref = {'work_id': work['id'], 'module_id': chunk['id']}
                result = push_to_outbox(
                    recipient_phone=channel_id,
                    recipient_name=channel_label,
                    content=content,
                    source='work_serializer',
                    scheduled_at=slot_iso,
                    source_ref=src_ref,
                )
                chunk['status']     = 'queued'
                chunk['message_id'] = result['id']

                action['message_id'] = result['id']
                occupied.append(slot['dt'])

            actions.append(action)

    # Persist changes
    if not dry_run:
        write_json(PROMO_WORKS_FILE, works_data)
        write_json(PROMO_PROVERBS_FILE, proverbs_data)

    return {
        'dry_run': dry_run,
        'actions': actions,
        'scheduled': len(actions),
        'proverbs_remaining': len(proverb_queue),
        'novel_chunks_remaining': len(novel_queue),
        'flash_chunks_remaining': len(flash_queue),
    }


# ── Clean-queue ────────────────────────────────────────────────────────────────

def _canonical_slot_time(msg, works_by_id, profiles_by_id):
    """
    Return the correct (hour, minute) SAST for a queued message based on
    the META-SCHEDULE v2 rules.

    Returns (hour, minute) or None if the message type is unknown.
    """
    source = msg.get('source', '')
    if source == 'wa_post_maker':
        # PROVERB: Mon-Sat 07:30, Sun 09:00
        try:
            sat  = msg['scheduled_at'].replace('Z', '+00:00')
            dt   = datetime.fromisoformat(sat).astimezone(SAST)
            return (9, 0) if dt.weekday() == 6 else (7, 30)
        except Exception:
            return None

    if source == 'work_serializer':
        ref      = msg.get('source_ref') or {}
        work_id  = ref.get('work_id', '')
        work     = works_by_id.get(work_id)
        if not work:
            return None
        profile  = profiles_by_id.get(work.get('profile_id', ''))
        if not profile:
            return None
        is_novel = profile.get('num_chunks') is None
        if is_novel:
            # VIP and Channel are both anchored to 12:15; channel = VIP + 24h (already stored)
            # Don't touch novel messages — they were scheduled intentionally.
            return None
        # Flash / short → 18:30 SAST
        return (18, 30)

    return None


def _clean_queue(dry_run=False):
    """
    Audit and repair the outbox queue:
    1. Fix messages whose scheduled_at doesn't match their canonical slot time.
    2. Remove duplicate messages sharing the same (date, source, canonical slot).

    Returns a dict with lists of fixes and deletions.
    """
    from services.distribution_service import _ec2_update, _ec2_delete

    settings     = read_json(PROMO_SETTINGS_FILE) or {}
    profiles_by_id = {p['id']: p for p in settings.get('serializer_profiles', [])}

    works_data   = read_json(PROMO_WORKS_FILE) or {'works': []}
    works_by_id  = {w['id']: w for w in works_data.get('works', [])}

    msgs_data    = read_json(PROMO_MESSAGES_FILE) or {'messages': []}
    msgs         = msgs_data['messages']
    queued       = [m for m in msgs if m.get('status') == 'queued']

    fixes        = []   # {id, old_time, new_time}
    deletions    = []   # {id, reason}

    # ── Step 1: Assign canonical times, group by (date, canonical_slot) ────────
    from collections import defaultdict
    slot_groups = defaultdict(list)   # (date, hour, min, source) → [msg]

    for msg in queued:
        sat = msg.get('scheduled_at', '')
        try:
            dt = datetime.fromisoformat(sat.replace('Z', '+00:00')).astimezone(SAST)
        except Exception:
            continue

        canon = _canonical_slot_time(msg, works_by_id, profiles_by_id)
        if canon is None:
            continue  # leave novel messages alone

        c_hour, c_min = canon
        slot_groups[(dt.date(), c_hour, c_min, msg.get('source'))].append({
            'msg': msg, 'current_dt': dt,
            'canon_hour': c_hour, 'canon_min': c_min,
        })

    # ── Step 2: For each slot group, keep one and fix/delete the rest ──────────
    for (day, c_hour, c_min, source), entries in slot_groups.items():
        # Sort by created_at to keep the earliest-created entry
        entries.sort(key=lambda e: e['msg'].get('created_at', ''))
        keeper = entries[0]
        extras = entries[1:]

        # Fix time on keeper if it differs from canonical
        keeper_dt     = keeper['current_dt']
        target_dt     = keeper_dt.replace(hour=c_hour, minute=c_min, second=0, microsecond=0)
        target_iso    = target_dt.replace(microsecond=0).isoformat()
        keeper_iso    = keeper_dt.replace(microsecond=0).isoformat()

        if keeper_iso != target_iso:
            fixes.append({
                'id':       keeper['msg']['id'],
                'source':   source,
                'old_time': keeper_iso,
                'new_time': target_iso,
                'content':  keeper['msg'].get('content', '')[:60],
            })
            if not dry_run:
                # Update local
                keeper['msg']['scheduled_at'] = target_iso
                keeper['msg']['updated_at']   = datetime.utcnow().isoformat() + 'Z'
                # Update EC2
                _ec2_update(keeper['msg']['id'], {'scheduled_at': target_iso})

        # Delete extras
        for entry in extras:
            msg = entry['msg']
            deletions.append({
                'id':       msg['id'],
                'source':   source,
                'time':     entry['current_dt'].replace(microsecond=0).isoformat(),
                'reason':   'duplicate slot',
                'content':  msg.get('content', '')[:60],
            })
            if not dry_run:
                # Remove from local list
                msgs_data['messages'] = [
                    m for m in msgs_data['messages'] if m['id'] != msg['id']
                ]
                # Reset proverb queue_status so it can be rescheduled
                if source == 'wa_post_maker' and msg.get('proverb_id'):
                    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {'proverbs': []}
                    for p in proverbs_data['proverbs']:
                        if p['id'] == msg['proverb_id']:
                            p['queue_status'] = None
                            p.pop('updated_at', None)
                            break
                    write_json(PROMO_PROVERBS_FILE, proverbs_data)
                # Delete from EC2
                _ec2_delete(msg['id'])

    if not dry_run and (fixes or deletions):
        write_json(PROMO_MESSAGES_FILE, msgs_data)

    return {
        'dry_run':    dry_run,
        'fixes':      fixes,
        'deletions':  deletions,
        'fixed':      len(fixes),
        'deleted':    len(deletions),
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@bp.route('/api/scheduler/preview', methods=['GET'])
def preview_schedule():
    """Dry-run — show what the scheduler would queue without writing anything."""
    try:
        result = _run(dry_run=True)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/scheduler/run', methods=['POST'])
def run_schedule():
    """Execute the scheduler and queue all available content."""
    dry_run = request.get_json(silent=True, force=True) or {}
    dry_run = bool(dry_run.get('dry_run', False))
    try:
        result = _run(dry_run=dry_run)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/scheduler/clean-queue', methods=['GET'])
def preview_clean_queue():
    """Dry-run audit — show what would be fixed/deleted without writing anything."""
    try:
        return jsonify(_clean_queue(dry_run=True))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/scheduler/clean-queue', methods=['POST'])
def execute_clean_queue():
    """Fix wrong slot times and remove duplicate messages in the outbox."""
    try:
        return jsonify(_clean_queue(dry_run=False))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
