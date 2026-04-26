"""
Auto-scheduler — implements INDABA SCHEDULING META-TEMPLATE v1.0

Content types:
  STORY       — work_serializer posts; serialized fiction chapters
  PROVERB     — wa_post_maker posts; proverb broadcast images
  ENGAGEMENT  — engagement posts
  CONVERSION  — conversion / CTA posts

Day types:
  STANDARD    — Monday–Saturday
  LIGHT       — Sunday only

Source → content type mapping:
  'work_serializer' → STORY
  'wa_post_maker'   → PROVERB
  'engagement'      → ENGAGEMENT
  'conversion'      → CONVERSION

scheduled_at is always stored and returned as UTC ISO 8601 string.
All window times in delivery_schedule are local (SAST, UTC+2 by default).
"""
from datetime import datetime, timedelta, timezone

# Priority order (lower number = higher priority)
TYPE_PRIORITY = {'STORY': 1, 'PROVERB': 2, 'ENGAGEMENT': 3, 'CONVERSION': 4}

# Source → content type
SOURCE_TYPE = {
    'work_serializer': 'STORY',
    'wa_post_maker':   'PROVERB',
    'engagement':      'ENGAGEMENT',
    'conversion':      'CONVERSION',
}

# Built-in slot definitions (used when delivery_schedule.slots not configured)
DEFAULT_STANDARD_SLOTS = [
    {'id': 'MORNING_PRIME',    'window_start': '06:30', 'window_end': '08:30',
     'allowed_types': ['PROVERB', 'ENGAGEMENT'], 'capacity': 1},
    {'id': 'MIDDAY_STORY_1',   'window_start': '11:30', 'window_end': '13:00',
     'allowed_types': ['STORY'],                 'capacity': 1},
    {'id': 'AFTERNOON_PROVERB','window_start': '14:00', 'window_end': '15:30',
     'allowed_types': ['PROVERB'],               'capacity': 1},
    {'id': 'AFTERNOON_PULSE',  'window_start': '16:00', 'window_end': '17:30',
     'allowed_types': ['ENGAGEMENT', 'CONVERSION'], 'capacity': 1},
    {'id': 'EVENING_STORY_2',  'window_start': '18:30', 'window_end': '20:30',
     'allowed_types': ['STORY'],                 'capacity': 1},
    {'id': 'NIGHT_CLOSE',      'window_start': '21:00', 'window_end': '22:30',
     'allowed_types': ['PROVERB', 'CONVERSION', 'STORY'], 'capacity': 1},
]

DEFAULT_LIGHT_SLOTS = [
    {'id': 'MORNING_LIGHT', 'window_start': '08:00', 'window_end': '10:00',
     'allowed_types': ['PROVERB'],            'capacity': 1},
    {'id': 'EVENING_LIGHT', 'window_start': '18:00', 'window_end': '20:00',
     'allowed_types': ['STORY', 'CONVERSION'], 'capacity': 1},
]

MAX_STORY_STANDARD = 2
MAX_STORY_LIGHT    = 1
MIN_GAP_MINUTES    = 90


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hhmm(s: str) -> int:
    h, m = map(int, s.split(':'))
    return h * 60 + m


def _local_dt(date, minutes: int, tz) -> datetime:
    return datetime(date.year, date.month, date.day,
                    minutes // 60, minutes % 60, 0, tzinfo=tz)


def _parse_utc(iso: str, local_tz) -> 'datetime | None':
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(local_tz)
    except (ValueError, AttributeError):
        return None


def _content_type(source: str) -> str:
    s = source.strip().lower()
    return SOURCE_TYPE.get(s, 'ENGAGEMENT')


def _is_light_day(date, lighter_day='Sunday') -> bool:
    return date.strftime('%A') == lighter_day


def _slots_for_day(is_light: bool, schedule: dict) -> list:
    stored = schedule.get('slots', {})
    if is_light:
        return stored.get('light', DEFAULT_LIGHT_SLOTS)
    return stored.get('standard', DEFAULT_STANDARD_SLOTS)


def _find_gap(date, slot_start: int, slot_end: int,
              day_posts: list, now_local: datetime, tz) -> 'datetime | None':
    """Scan the slot in 5-min steps for a time that clears the 90-min gap rule."""
    m = slot_start
    while m < slot_end:
        cand = _local_dt(date, m, tz)
        if cand > now_local:
            if all(abs((cand - dt).total_seconds()) >= MIN_GAP_MINUTES * 60
                   for dt in day_posts):
                return cand
        m += 5
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def auto_schedule(content_type_or_source: str, existing_queue: list,
                  schedule: dict, fail_if_full: bool = False) -> 'str | None':
    """
    Return the next available UTC ISO scheduled_at for a single item.

    content_type_or_source : source string ('wa_post_maker', 'work_serializer', …)
                             OR upper-case type ('PROVERB', 'STORY', …)
    existing_queue         : list of dicts with 'scheduled_at' ISO strings
    schedule               : delivery_schedule dict from promo_settings.json
    fail_if_full           : return None instead of fallback when no slot found
    """
    tz_offset   = int(schedule.get('tz_offset_hours', 2))
    local_tz    = timezone(timedelta(hours=tz_offset))
    lighter_day = schedule.get('lighter_day', 'Sunday')

    # Normalise to upper-case type
    ctype = _content_type(content_type_or_source)
    if content_type_or_source.upper() in TYPE_PRIORITY:
        ctype = content_type_or_source.upper()

    # Parse existing scheduled datetimes
    existing_local = [
        dt for dt in (_parse_utc(m.get('scheduled_at', ''), local_tz)
                      for m in existing_queue)
        if dt is not None
    ]

    now_local = datetime.now(timezone.utc).astimezone(local_tz)

    for day_offset in range(90):
        cand_date  = (now_local + timedelta(days=day_offset)).date()
        is_light   = _is_light_day(cand_date, lighter_day)
        slots      = _slots_for_day(is_light, schedule)

        day_posts  = [dt for dt in existing_local if dt.date() == cand_date]

        # Story cap
        if ctype == 'STORY':
            story_count = sum(
                1 for m in existing_queue
                if _content_type(m.get('source', '')) == 'STORY'
                and (ldt := _parse_utc(m.get('scheduled_at', ''), local_tz)) is not None
                and ldt.date() == cand_date
            )
            max_s = MAX_STORY_LIGHT if is_light else MAX_STORY_STANDARD
            if story_count >= max_s:
                continue

        for slot in slots:
            if ctype not in slot['allowed_types']:
                continue

            slot_start = _hhmm(slot['window_start'])
            slot_end   = _hhmm(slot['window_end'])

            slot_posts = [
                dt for dt in day_posts
                if slot_start <= dt.hour * 60 + dt.minute < slot_end
            ]
            if len(slot_posts) >= slot['capacity']:
                continue

            assign_min = (slot_start + slot_end) // 2
            cand_local = _local_dt(cand_date, assign_min, local_tz)

            if cand_local <= now_local:
                continue

            too_close = any(
                abs((cand_local - dt).total_seconds()) < MIN_GAP_MINUTES * 60
                for dt in day_posts
            )
            if too_close:
                cand_local = _find_gap(
                    cand_date, slot_start, slot_end, day_posts, now_local, local_tz)
                if cand_local is None:
                    continue

            return cand_local.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    if fail_if_full:
        return None
    return (datetime.now(timezone.utc) + timedelta(hours=24)).replace(microsecond=0).isoformat()


def reschedule_batch(messages: list, schedule: dict) -> list:
    """
    Assign new scheduled_at timestamps to a batch of messages following the
    meta-template. Stories are prioritised and sequenced first.

    messages : list of message dicts (must have 'id', 'source')
    schedule : delivery_schedule dict from promo_settings.json
    Returns  : list of {id, scheduled_at} in assignment order
    """
    tz_offset   = int(schedule.get('tz_offset_hours', 2))
    local_tz    = timezone(timedelta(hours=tz_offset))
    lighter_day = schedule.get('lighter_day', 'Sunday')

    # Sort: STORY first (preserve original order within type), then others
    def sort_key(m):
        return TYPE_PRIORITY.get(_content_type(m.get('source', '')), 99)

    ordered = sorted(messages, key=sort_key)

    assigned       = []    # [{id, scheduled_at}]
    assigned_queue = []    # pseudo-queue fed to subsequent iterations

    now_local = datetime.now(timezone.utc).astimezone(local_tz)

    for msg in ordered:
        source = msg.get('source', 'engagement')
        ctype  = _content_type(source)

        placed = False
        for day_offset in range(90):
            cand_date  = (now_local + timedelta(days=day_offset)).date()
            is_light   = _is_light_day(cand_date, lighter_day)
            slots      = _slots_for_day(is_light, schedule)

            day_posted = [
                dt for dt in (
                    _parse_utc(a['scheduled_at'], local_tz) for a in assigned_queue
                ) if dt is not None and dt.date() == cand_date
            ]

            if ctype == 'STORY':
                day_stories = sum(
                    1 for a in assigned_queue
                    if _content_type(a.get('source', '')) == 'STORY'
                    and (ldt := _parse_utc(a['scheduled_at'], local_tz)) is not None
                    and ldt.date() == cand_date
                )
                max_s = MAX_STORY_LIGHT if is_light else MAX_STORY_STANDARD
                if day_stories >= max_s:
                    continue

            for slot in slots:
                if ctype not in slot['allowed_types']:
                    continue

                slot_start = _hhmm(slot['window_start'])
                slot_end   = _hhmm(slot['window_end'])

                slot_posts = [
                    dt for dt in day_posted
                    if slot_start <= dt.hour * 60 + dt.minute < slot_end
                ]
                if len(slot_posts) >= slot['capacity']:
                    continue

                if not slot_posts:
                    assign_min = (slot_start + slot_end) // 2
                else:
                    latest_min = max(dt.hour * 60 + dt.minute for dt in slot_posts)
                    assign_min = latest_min + MIN_GAP_MINUTES
                    if assign_min >= slot_end:
                        continue

                cand_local = _local_dt(cand_date, assign_min, local_tz)

                if cand_local <= now_local:
                    continue

                too_close = any(
                    abs((cand_local - dt).total_seconds()) < MIN_GAP_MINUTES * 60
                    for dt in day_posted
                )
                if too_close:
                    cand_local = _find_gap(
                        cand_date, slot_start, slot_end, day_posted, now_local, local_tz)
                    if cand_local is None:
                        continue

                sat_utc = cand_local.astimezone(timezone.utc).replace(microsecond=0).isoformat()
                assigned.append({'id': msg['id'], 'scheduled_at': sat_utc})
                assigned_queue.append({
                    'id': msg['id'], 'scheduled_at': sat_utc,
                    'source': source, 'status': 'queued'
                })
                placed = True
                break

            if placed:
                break

    return assigned
