"""
Shared helper utilities for Indaba.
"""
from datetime import datetime, date, timedelta
from utils.json_store import read_json, write_json
from utils.constants import _DEFAULTS, PROMO_MESSAGES_FILE


def get_constants():
    """Return editable constants, merging settings.json overrides with defaults."""
    s = read_json('settings.json') or {}
    c = dict(_DEFAULTS)
    for k in _DEFAULTS:
        if k in s:
            try:
                c[k] = int(s[k])
            except (ValueError, TypeError):
                pass
    c['zone_caps'] = {
        'morning':   c['zone_cap_morning'],
        'paid_work': c['zone_cap_paid_work'],
        'evening':   c['zone_cap_evening'],
    }
    return c


def deadline_info(deadline_str):
    """Return (label, urgency_class) for a deadline string."""
    if not deadline_str:
        return None, None
    try:
        dl    = date.fromisoformat(deadline_str)
        today = date.today()
        delta = (dl - today).days
        if delta < 0:
            return f'OVERDUE ({abs(delta)}d)', 'overdue'
        elif delta == 0:
            return 'Today', 'urgent'
        elif delta == 1:
            return 'Tomorrow', 'urgent'
        elif delta <= 4:
            return f'{delta} days', 'urgent'
        elif delta <= 10:
            return f'{delta} days', 'soon'
        else:
            return dl.strftime('%d %b'), 'ok'
    except ValueError:
        return deadline_str, 'ok'


def posting_streak(log, platform):
    """Count consecutive days (including today) where platform was posted."""
    streak = 0
    d = date.today()
    while True:
        key = d.isoformat()
        if log.get(key, {}).get(platform, False):
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak


def process_overdue_queue():
    """Identify and flag queued messages that missed their scheduled time."""
    data     = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    messages = data.get("messages", [])
    now_str  = datetime.utcnow().isoformat() + "Z"
    changed  = 0
    for m in messages:
        if m.get("status") == "queued" and m.get("scheduled_at"):
            try:
                sched = datetime.fromisoformat(m["scheduled_at"].replace("Z", "+00:00"))
                now   = datetime.fromisoformat(now_str.replace("Z", "+00:00"))
                if sched <= now:
                    m["status"] = "overdue"
                    changed += 1
            except (ValueError, TypeError):
                pass
    if changed > 0:
        write_json(PROMO_MESSAGES_FILE, data)
    return changed
