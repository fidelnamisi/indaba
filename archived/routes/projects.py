"""
Project management routes — projects, inbox, dormant, caps, daily log,
posting log, lead measures, earnings.
"""
import uuid
from datetime import datetime, date, timedelta

from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json
from utils.constants import (
    INBOX_FILE, DORMANT_FILE, POSTING_LOG_FILE, POSTING_PLATFORMS,
    EARNINGS_FILE, INBOX_MAX, DORMANT_MAX, INBOX_EXPIRY_DAYS
)
from utils.helpers import get_constants, deadline_info, posting_streak

bp = Blueprint('projects', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _purge_inbox():
    inbox   = read_json(INBOX_FILE) or []
    now_iso = datetime.now().isoformat()
    live    = [item for item in inbox if item.get('expires_at', '9999') > now_iso]
    if len(live) < len(inbox):
        write_json(INBOX_FILE, live)
    return live


# ── Projects ──────────────────────────────────────────────────────────────────

@bp.route('/api/projects', methods=['GET'])
def get_projects():
    return jsonify(read_json('projects.json') or [])


@bp.route('/api/projects', methods=['POST'])
def create_project():
    data     = request.get_json()
    projects = read_json('projects.json') or []
    now      = datetime.now().isoformat()
    project  = {
        'id':                   str(uuid.uuid4()),
        'name':                 data.get('name', 'Untitled'),
        'type':                 data.get('type', 'other'),
        'pipeline':             data.get('pipeline', 'creative_development'),
        'phase':                data.get('phase', ''),
        'phases':               data.get('phases', []),
        'next_action':          data.get('next_action', ''),
        'deadline':             data.get('deadline'),
        'blocked':              data.get('blocked', False),
        'blocked_reason':       data.get('blocked_reason'),
        'priority':             int(data.get('priority', 3)),
        'money_attached':       data.get('money_attached', False),
        'notes':                data.get('notes', ''),
        'source':               data.get('source', ''),
        'living_writer_record': data.get('living_writer_record', False),
        'crm_record':           data.get('crm_record', False),
        'mission_critical':     data.get('mission_critical', False),
        'energy_zone':          data.get('energy_zone', 'flexible'),
        'completed':            False,
        'completed_at':         None,
        'last_session_note':    '',
        'last_session_at':      None,
        'zone_priority':        False,
        'gw_lifecycle': {
            'commission_confirmed': False, 'draft_delivered':   False,
            'revision_complete':    False, 'final_delivered':   False,
            'invoice_sent':         False, 'payment_received':  False,
        },
        'created_at': now,
        'updated_at': now,
    }
    projects.append(project)
    write_json('projects.json', projects)
    return jsonify(project), 201


@bp.route('/api/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    data     = request.get_json()
    projects = read_json('projects.json') or []
    for i, p in enumerate(projects):
        if p['id'] == project_id:
            if 'completed' in data and data['completed'] != p.get('completed', False):
                data['completed_at'] = datetime.now().isoformat() if data['completed'] else None
            data['id']         = project_id
            data['created_at'] = p.get('created_at')
            data['updated_at'] = datetime.now().isoformat()
            projects[i]        = {**p, **data}
            write_json('projects.json', projects)
            return jsonify(projects[i])
    return jsonify({'error': 'Not found'}), 404


@bp.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    projects = read_json('projects.json') or []
    write_json('projects.json', [p for p in projects if p['id'] != project_id])
    return jsonify({'ok': True})


@bp.route('/api/projects/<project_id>/session-note', methods=['POST'])
def log_session_note(project_id):
    data     = request.get_json()
    note     = data.get('note', '').strip()
    projects = read_json('projects.json') or []
    for i, p in enumerate(projects):
        if p['id'] == project_id:
            projects[i]['last_session_note'] = note
            projects[i]['last_session_at']   = datetime.now().isoformat()
            projects[i]['updated_at']         = datetime.now().isoformat()
            write_json('projects.json', projects)
            today_key = date.today().isoformat()
            daily_log = read_json('daily_log.json') or {}
            entry     = daily_log.get(today_key, {'commitment': '', 'session_notes': []})
            entry.setdefault('session_notes', []).append({
                'project_id':   project_id,
                'project_name': p.get('name', ''),
                'note':         note,
                'at':           projects[i]['last_session_at'],
            })
            daily_log[today_key] = entry
            write_json('daily_log.json', daily_log)
            return jsonify(projects[i])
    return jsonify({'error': 'Not found'}), 404


@bp.route('/api/projects/<project_id>/set-zone-priority', methods=['POST'])
def set_zone_priority(project_id):
    projects = read_json('projects.json') or []
    target   = next((p for p in projects if p['id'] == project_id), None)
    if not target:
        return jsonify({'error': 'Not found'}), 404
    if target.get('completed'):
        return jsonify({'error': 'Cannot set focus on a completed project'}), 400
    zone     = target.get('energy_zone', 'paid_work')
    existing = next((p for p in projects if p['id'] != project_id
                     and p.get('energy_zone') == zone
                     and p.get('zone_priority') and not p.get('completed')), None)
    if existing:
        return jsonify({
            'error':          f'"{existing["name"]}" already holds focus for this zone. Release it first.',
            'conflict_id':    existing['id'],
            'conflict_name':  existing['name'],
        }), 409
    for p in projects:
        if p['id'] == project_id:
            p['zone_priority'] = True
            p['updated_at']    = datetime.now().isoformat()
    write_json('projects.json', projects)
    return jsonify({'ok': True})


@bp.route('/api/projects/<project_id>/release-zone-priority', methods=['POST'])
def release_zone_priority(project_id):
    projects = read_json('projects.json') or []
    for p in projects:
        if p['id'] == project_id:
            p['zone_priority'] = False
            p['updated_at']    = datetime.now().isoformat()
            write_json('projects.json', projects)
            return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404


# ── Daily log ─────────────────────────────────────────────────────────────────

@bp.route('/api/daily-log', methods=['GET'])
def get_daily_log():
    date_key  = request.args.get('date', date.today().isoformat())
    daily_log = read_json('daily_log.json') or {}
    return jsonify(daily_log.get(date_key, {'commitment': '', 'session_notes': []}))


@bp.route('/api/daily-log', methods=['PUT'])
def update_daily_log():
    data      = request.get_json()
    date_key  = data.get('date', date.today().isoformat())
    daily_log = read_json('daily_log.json') or {}
    entry     = daily_log.get(date_key, {'commitment': '', 'session_notes': []})
    if 'commitment' in data:
        entry['commitment'] = data['commitment']
    daily_log[date_key] = entry
    write_json('daily_log.json', daily_log)
    return jsonify(entry)


# ── Inbox ─────────────────────────────────────────────────────────────────────

@bp.route('/api/inbox', methods=['GET'])
def get_inbox():
    return jsonify(_purge_inbox())


@bp.route('/api/inbox', methods=['POST'])
def create_inbox_item():
    inbox = _purge_inbox()
    if len(inbox) >= INBOX_MAX:
        return jsonify({'error': f'Inbox is full ({INBOX_MAX} items). Triage something before adding more.'}), 409
    data  = request.get_json()
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    captured = datetime.now()
    item = {
        'id':          str(uuid.uuid4())[:8],
        'title':       title,
        'notes':       (data.get('notes') or '').strip(),
        'captured_at': captured.isoformat(),
        'expires_at':  (captured + timedelta(days=INBOX_EXPIRY_DAYS)).isoformat(),
    }
    inbox.append(item)
    write_json(INBOX_FILE, inbox)
    return jsonify(item), 201


@bp.route('/api/inbox/<item_id>', methods=['DELETE'])
def delete_inbox_item(item_id):
    inbox = read_json(INBOX_FILE) or []
    write_json(INBOX_FILE, [i for i in inbox if i['id'] != item_id])
    return jsonify({'ok': True})


@bp.route('/api/inbox/<item_id>/archive', methods=['POST'])
def archive_inbox_item(item_id):
    inbox   = _purge_inbox()
    dormant = read_json(DORMANT_FILE) or []
    if len(dormant) >= DORMANT_MAX:
        return jsonify({'error': f'Dormant archive is full ({DORMANT_MAX} ideas). Delete something first.'}), 409
    item = next((i for i in inbox if i['id'] == item_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    dormant.append({
        'id':                   item['id'],
        'title':                item['title'],
        'notes':                item.get('notes', ''),
        'archived_at':          datetime.now().isoformat(),
        'original_captured_at': item.get('captured_at', ''),
    })
    write_json(DORMANT_FILE, dormant)
    write_json(INBOX_FILE, [i for i in inbox if i['id'] != item_id])
    return jsonify({'ok': True})


@bp.route('/api/inbox/<item_id>/promote', methods=['POST'])
def promote_inbox_item(item_id):
    inbox    = _purge_inbox()
    projects = read_json('projects.json') or []
    item     = next((i for i in inbox if i['id'] == item_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    data        = request.get_json() or {}
    energy_zone = data.get('energy_zone', 'paid_work')
    active      = [p for p in projects if not p.get('completed')]
    consts      = get_constants()
    if len(active) >= consts['total_project_cap']:
        return jsonify({'error': f'Project cap reached ({consts["total_project_cap"]} active). Complete or remove one first.'}), 409
    zone_count = sum(1 for p in active if p.get('energy_zone') == energy_zone)
    zone_cap   = consts['zone_caps'].get(energy_zone, 99)
    if zone_count >= zone_cap:
        label = energy_zone.replace('_', ' ').title()
        return jsonify({'error': f'{label} zone is full ({zone_cap} projects). Complete or move one first.'}), 409
    now     = datetime.now().isoformat()
    project = {
        'id':                   str(uuid.uuid4()),
        'name':                 data.get('name', item['title']),
        'type':                 data.get('type', 'other'),
        'pipeline':             data.get('pipeline', 'creative_development'),
        'phase':                data.get('phase', ''),
        'phases':               [],
        'next_action':          data.get('next_action', ''),
        'deadline':             data.get('deadline'),
        'blocked':              False,
        'blocked_reason':       None,
        'priority':             int(data.get('priority', 3)),
        'money_attached':       data.get('money_attached', False),
        'notes':                item.get('notes', ''),
        'source':               'inbox',
        'living_writer_record': False,
        'crm_record':           False,
        'mission_critical':     data.get('mission_critical', False),
        'energy_zone':          energy_zone,
        'completed':            False,
        'completed_at':         None,
        'last_session_note':    '',
        'last_session_at':      None,
        'zone_priority':        False,
        'gw_lifecycle': {
            'commission_confirmed': False, 'draft_delivered':   False,
            'revision_complete':    False, 'final_delivered':   False,
            'invoice_sent':         False, 'payment_received':  False,
        },
        'created_at': now,
        'updated_at': now,
    }
    projects.append(project)
    write_json('projects.json', projects)
    write_json(INBOX_FILE, [i for i in inbox if i['id'] != item_id])
    return jsonify(project), 201


# ── Dormant ───────────────────────────────────────────────────────────────────

@bp.route('/api/dormant', methods=['GET'])
def get_dormant():
    return jsonify(read_json(DORMANT_FILE) or [])


@bp.route('/api/dormant/<item_id>', methods=['DELETE'])
def delete_dormant_item(item_id):
    dormant = read_json(DORMANT_FILE) or []
    write_json(DORMANT_FILE, [i for i in dormant if i['id'] != item_id])
    return jsonify({'ok': True})


@bp.route('/api/dormant/<item_id>/revive', methods=['POST'])
def revive_dormant_item(item_id):
    dormant = read_json(DORMANT_FILE) or []
    inbox   = _purge_inbox()
    if len(inbox) >= INBOX_MAX:
        return jsonify({'error': f'Inbox full ({INBOX_MAX} items). Triage first.'}), 409
    item = next((i for i in dormant if i['id'] == item_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    captured = datetime.now()
    inbox.append({
        'id':          item['id'],
        'title':       item['title'],
        'notes':       item.get('notes', ''),
        'captured_at': captured.isoformat(),
        'expires_at':  (captured + timedelta(days=INBOX_EXPIRY_DAYS)).isoformat(),
    })
    write_json(INBOX_FILE, inbox)
    write_json(DORMANT_FILE, [i for i in dormant if i['id'] != item_id])
    return jsonify({'ok': True})


# ── Caps ──────────────────────────────────────────────────────────────────────

@bp.route('/api/caps', methods=['GET'])
def get_caps():
    projects = read_json('projects.json') or []
    active   = [p for p in projects if not p.get('completed')]
    inbox    = _purge_inbox()
    dormant  = read_json(DORMANT_FILE) or []
    consts   = get_constants()
    return jsonify({
        'total_active':  len(active),
        'total_cap':     consts['total_project_cap'],
        'zone_counts':   {z: sum(1 for p in active if p.get('energy_zone') == z) for z in consts['zone_caps']},
        'zone_caps':     consts['zone_caps'],
        'inbox_count':   len(inbox),
        'inbox_max':     consts['inbox_max'],
        'dormant_count': len(dormant),
        'dormant_max':   consts['dormant_max'],
    })


# ── Posting log ───────────────────────────────────────────────────────────────

@bp.route('/api/posting-log', methods=['GET'])
def get_posting_log():
    date_key = request.args.get('date', date.today().isoformat())
    log      = read_json(POSTING_LOG_FILE) or {}
    entry    = log.get(date_key, {p: False for p in POSTING_PLATFORMS})
    streaks  = {p: posting_streak(log, p) for p in POSTING_PLATFORMS}
    return jsonify({'date': date_key, 'posting': entry, 'streaks': streaks})


@bp.route('/api/posting-log/toggle', methods=['POST'])
def toggle_posting():
    data     = request.get_json()
    platform = data.get('platform')
    date_key = data.get('date', date.today().isoformat())
    if platform not in POSTING_PLATFORMS:
        return jsonify({'error': f'Unknown platform: {platform}'}), 400
    log        = read_json(POSTING_LOG_FILE) or {}
    entry      = log.get(date_key, {p: False for p in POSTING_PLATFORMS})
    entry[platform] = not entry.get(platform, False)
    log[date_key]   = entry
    write_json(POSTING_LOG_FILE, log)
    streaks = {p: posting_streak(log, p) for p in POSTING_PLATFORMS}
    return jsonify({'date': date_key, 'posting': entry, 'streaks': streaks})


# ── Lead measures ─────────────────────────────────────────────────────────────

@bp.route('/api/lead-measures', methods=['GET'])
def get_lead_measures():
    all_measures = read_json('lead_measures.json') or {}
    month_key    = date.today().strftime('%Y-%m')
    return jsonify(all_measures.get(month_key, {}))


@bp.route('/api/lead-measures', methods=['PUT'])
def update_lead_measures():
    data         = request.get_json()
    all_measures = read_json('lead_measures.json') or {}
    month_key    = date.today().strftime('%Y-%m')
    current      = all_measures.get(month_key, {
        'pitches_sent': 0, 'pitch_meetings': 0,
        'in_active_review': 0, 'patreon_leads': 0, 'follow_ups': 0
    })
    for k, v in data.items():
        if str(v) == '+1':
            current[k] = current.get(k, 0) + 1
        elif str(v) == '-1':
            current[k] = max(0, current.get(k, 0) - 1)
        else:
            current[k] = int(v)
    all_measures[month_key] = current
    write_json('lead_measures.json', all_measures)
    return jsonify(current)


# ── Earnings ──────────────────────────────────────────────────────────────────

@bp.route('/api/earnings', methods=['GET'])
def list_earnings():
    return jsonify(read_json(EARNINGS_FILE) or [])


@bp.route('/api/earnings', methods=['POST'])
def create_earning():
    data = request.get_json()
    if not data or 'date' not in data or 'platform' not in data or 'amount' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    earnings = read_json(EARNINGS_FILE) or []
    entry    = {
        'id':       str(uuid.uuid4())[:8],
        'date':     data['date'],
        'platform': data['platform'],
        'amount':   float(data['amount']),
        'notes':    data.get('notes', ''),
    }
    earnings.append(entry)
    write_json(EARNINGS_FILE, earnings)
    return jsonify(entry), 201


@bp.route('/api/earnings/<entry_id>', methods=['DELETE'])
def delete_earning(entry_id):
    earnings = read_json(EARNINGS_FILE) or []
    filtered = [e for e in earnings if e.get('id') != entry_id]
    if len(filtered) == len(earnings):
        return jsonify({'error': 'Not found'}), 404
    write_json(EARNINGS_FILE, filtered)
    return jsonify({'ok': True})


@bp.route('/api/earnings/monthly', methods=['GET'])
def monthly_earnings():
    earnings = read_json(EARNINGS_FILE) or []
    monthly  = {}
    for e in earnings:
        month           = e['date'][:7]
        monthly[month]  = monthly.get(month, 0) + e['amount']
    result = [{'month': m, 'total': round(t, 2)} for m, t in monthly.items()]
    result.sort(key=lambda x: x['month'], reverse=True)
    return jsonify(result)
