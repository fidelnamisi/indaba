#!/usr/bin/env python3
"""Indaba Sender — minimal WhatsApp queue relay with status dashboard."""
import hashlib, hmac, json, os, uuid, threading, time, logging
import requests as _req
from datetime import datetime, timezone, timedelta
from functools import wraps

log = logging.getLogger('indaba-sender')

SAST = timezone(timedelta(hours=2))

def fmt_sast(iso_str):
    if not iso_str:
        return ''
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.astimezone(SAST).strftime('%a %-d %b %H:%M')
    except Exception:
        return iso_str[:16]
from flask import Flask, request, jsonify, Response

app = Flask(__name__)
QUEUE_FILE   = '/opt/indaba-sender/data/queue.json'
INBOUND_FILE = '/opt/indaba-sender/data/inbound.json'
WEBHOOK_SECRET = 'indaba-wa-secret'   # must match --webhook-secret in docker-compose

GOWA_URL         = os.environ.get('GOWA_BASE_URL', 'http://localhost:3000')
GOWA_AUTH        = os.environ.get('GOWA_AUTH', 'admin:admin')
GOWA_DEVICE_NAME = 'indaba-fidel'   # fixed device ID — stable across GoWA restarts

# Watchdog state
_gowa_state      = {'status': 'unknown', 'checked_at': ''}  # shared dict, updated by watchdog

def load_queue():
    if not os.path.exists(QUEUE_FILE): return []
    with open(QUEUE_FILE) as f: return json.load(f)

def save_queue(q):
    tmp = QUEUE_FILE + '.tmp'
    with open(tmp, 'w') as f: json.dump(q, f, indent=2)
    os.replace(tmp, QUEUE_FILE)

# ── Inbound store ─────────────────────────────────────────────────────────────

def load_inbound():
    if not os.path.exists(INBOUND_FILE): return []
    with open(INBOUND_FILE) as f:
        try: return json.load(f)
        except Exception: return []

def save_inbound(msgs):
    os.makedirs(os.path.dirname(INBOUND_FILE), exist_ok=True)
    tmp = INBOUND_FILE + '.tmp'
    with open(tmp, 'w') as f: json.dump(msgs, f, indent=2)
    os.replace(tmp, INBOUND_FILE)

def _extract_inbound(payload):
    """
    Pull sender phone, text body, and timestamp out of a GoWA webhook event.
    Returns None if the event is not an inbound text message from a real person.

    GoWA v8.3+ webhook shape:
      { "device_id": "...", "event": "message",
        "payload": { "body": "...", "chat_id": "...", "from": "2782...@s.whatsapp.net",
                     "from_name": "...", "id": "...", "is_from_me": false,
                     "timestamp": "..." } }

    Legacy shape (pre-v8.3):
      { "code": "message", "results": { "from": "...", "is_from_me": false,
        "message": { "conversation": "..." }, "timestamp": "..." } }
    """
    # ── GoWA v8.3+ ───────────────────────────────────────────────────────────
    if payload.get('event') == 'message':
        inner = payload.get('payload') or {}
        if inner.get('is_from_me'):
            return None
        chat_id = inner.get('chat_id', '')
        # Skip group and newsletter messages — only relay direct messages
        if chat_id.endswith('@g.us') or chat_id.endswith('@newsletter'):
            return None
        from_raw = inner.get('from', '').strip()
        phone = from_raw.split('@')[0].replace('+', '').strip()
        if not phone or not phone.isdigit():
            return None
        text = (inner.get('body') or inner.get('text') or '').strip()
        if not text:
            return None
        ts_raw = inner.get('timestamp', '')
        ts = ts_raw if ts_raw else datetime.now(timezone.utc).isoformat()
        return {
            'id':        str(uuid.uuid4()),
            'phone':     phone,
            'from_name': inner.get('from_name') or '',
            'text':      text,
            'timestamp': ts,
            'consumed':  False,
            'raw_event': payload,
        }

    # ── Legacy GoWA (pre-v8.3) ───────────────────────────────────────────────
    results = payload.get('results') or payload.get('data') or payload
    if not isinstance(results, dict):
        return None
    if results.get('is_from_me') or results.get('is_group'):
        return None
    from_raw = (results.get('from') or results.get('sender') or '').strip()
    phone = from_raw.split('@')[0].replace('+', '').strip()
    if not phone or not phone.isdigit():
        return None
    text = ''
    msg = results.get('message') or {}
    if isinstance(msg, str):
        text = msg
    elif isinstance(msg, dict):
        text = (msg.get('conversation')
                or msg.get('text')
                or (msg.get('extendedTextMessage') or {}).get('text')
                or (msg.get('imageMessage') or {}).get('caption')
                or '')
    if not text:
        text = results.get('body') or results.get('text') or results.get('content') or ''
    text = text.strip()
    if not text:
        return None
    ts_raw = results.get('timestamp') or results.get('message_timestamp') or ''
    if isinstance(ts_raw, (int, float)):
        ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc).isoformat()
    elif ts_raw:
        ts = ts_raw
    else:
        ts = datetime.now(timezone.utc).isoformat()
    return {
        'id':        str(uuid.uuid4()),
        'phone':     phone,
        'from_name': results.get('from_name') or results.get('push_name') or '',
        'text':      text,
        'timestamp': ts,
        'consumed':  False,
        'raw_event': payload,
    }

def _gowa_auth():
    u, p = GOWA_AUTH.split(':', 1)
    return (u, p)

def _ensure_device():
    """Create the fixed device in GoWA if it doesn't exist yet. Safe to call repeatedly."""
    try:
        r = _req.get(f'{GOWA_URL}/devices', auth=_gowa_auth(), timeout=5)
        if r.status_code == 200:
            devices = r.json().get('results') or []
            ids = [d.get('id') or d.get('device') for d in devices]
            if GOWA_DEVICE_NAME in ids:
                return True
        # Device not found — create it
        r2 = _req.post(f'{GOWA_URL}/devices',
                       json={'device_id': GOWA_DEVICE_NAME},
                       auth=_gowa_auth(), timeout=5)
        return r2.status_code == 200
    except Exception as e:
        log.warning('_ensure_device error: %s', e)
        return False

def _get_device_state():
    """
    Return (state, detail) where state is one of:
      'logged_in'    — connected and authenticated, ready to send
      'disconnected' — session exists but WebSocket dropped, try reconnect
      'needs_login'  — no session or REMOTE_LOGOUT, must scan QR
      'error'        — GoWA unreachable
    """
    try:
        r = _req.get(f'{GOWA_URL}/devices', auth=_gowa_auth(), timeout=5)
        if r.status_code != 200:
            return 'error', f'GET /devices → {r.status_code}'
        devices = r.json().get('results') or []
        dev = next((d for d in devices if (d.get('id') or d.get('device')) == GOWA_DEVICE_NAME), None)
        if not dev:
            return 'needs_login', 'device not found'
        state = dev.get('state', 'unknown')
        if state == 'logged_in':
            return 'logged_in', dev.get('jid', '')
        elif state == 'disconnected':
            # Session may still be valid — try reconnect
            return 'disconnected', 'session exists, connection dropped'
        else:
            return 'needs_login', state
    except Exception as e:
        return 'error', str(e)

def _attempt_reconnect():
    """
    Call GET /app/reconnect on GoWA with our device ID.
    Returns True if reconnect succeeded, False otherwise.
    """
    try:
        r = _req.get(f'{GOWA_URL}/app/reconnect',
                     headers={'X-Device-Id': GOWA_DEVICE_NAME},
                     auth=_gowa_auth(), timeout=10)
        data = r.json()
        if r.status_code == 200 and data.get('code') == 'SUCCESS':
            log.info('GoWA reconnect succeeded')
            return True
        log.warning('GoWA reconnect failed: %s', data.get('message'))
        return False
    except Exception as e:
        log.warning('GoWA reconnect error: %s', e)
        return False

def get_device_id():
    """Return GOWA_DEVICE_NAME if GoWA says the device is logged_in, else ''."""
    state, _ = _get_device_state()
    if state == 'logged_in':
        return GOWA_DEVICE_NAME
    return ''

def _watchdog_loop():
    """Background thread: every 60s check GoWA connection, reconnect if dropped."""
    # Give Flask time to start before first check
    time.sleep(15)
    while True:
        try:
            _ensure_device()
            state, detail = _get_device_state()
            now = datetime.now(timezone.utc).isoformat()
            _gowa_state['checked_at'] = now

            if state == 'logged_in':
                _gowa_state['status'] = 'connected'

            elif state == 'disconnected':
                _gowa_state['status'] = 'reconnecting'
                log.info('GoWA disconnected — attempting reconnect')
                ok = _attempt_reconnect()
                if ok:
                    _gowa_state['status'] = 'connected'
                else:
                    # Reconnect failed — session may be gone, needs QR
                    _gowa_state['status'] = 'needs_login'
                    _write_needs_login_alert()

            elif state == 'needs_login':
                _gowa_state['status'] = 'needs_login'
                _write_needs_login_alert()

            elif state == 'error':
                _gowa_state['status'] = 'error'
                log.warning('GoWA unreachable: %s', detail)

        except Exception as e:
            log.error('Watchdog error: %s', e)

        time.sleep(60)

def _write_needs_login_alert():
    """Write a flag file that Indaba's health check can surface to Fidel."""
    alert_file = '/opt/indaba-sender/data/gowa_needs_login.flag'
    os.makedirs(os.path.dirname(alert_file), exist_ok=True)
    with open(alert_file, 'w') as f:
        f.write(datetime.now(timezone.utc).isoformat())
    log.warning('GoWA needs QR re-login — flag written to %s', alert_file)

def require_auth(f):
    @wraps(f)
    def dec(*a, **kw):
        auth = request.authorization
        if not auth or auth.username != 'admin' or auth.password != 'admin':
            return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Indaba Sender"'})
        return f(*a, **kw)
    return dec

def send_via_gowa(msg, device_id):
    u, p = GOWA_AUTH.split(':', 1)
    is_image = bool(msg.get('media_url'))
    headers = {'X-Device-Id': device_id}
    try:
        if is_image:
            ep = f'{GOWA_URL}/send/image'
            payload = {'phone': msg['recipient_phone'], 'image_url': msg['media_url'],
                       'caption': msg.get('content', '')}
        else:
            ep = f'{GOWA_URL}/send/message'
            payload = {'phone': msg['recipient_phone'], 'message': msg['content']}
        r = _req.post(ep, json=payload, auth=(u, p), headers=headers, timeout=30)
        data = r.json()
        if r.status_code == 200 and data.get('code') == 'SUCCESS':
            return {'ok': True}
        return {'ok': False, 'error': data.get('message', 'GoWA error')}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

@app.route('/queue', methods=['GET'])
@require_auth
def list_queue():
    return jsonify(load_queue())

@app.route('/queue', methods=['POST'])
@require_auth
def enqueue():
    msg = request.json or {}
    if not msg.get('id'): msg['id'] = str(uuid.uuid4())
    msg.setdefault('status', 'queued')
    msg['cloud_queued_at'] = datetime.now(timezone.utc).isoformat()
    q = load_queue()
    if not any(m.get('id') == msg['id'] for m in q):
        q.append(msg)
        save_queue(q)
    return jsonify({'ok': True, 'queue_size': len([m for m in q if m.get('status') == 'queued'])})

@app.route('/queue/<msg_id>', methods=['PUT'])
@require_auth
def update_queue_message(msg_id):
    q = load_queue()
    msg = next((m for m in q if m.get('id') == msg_id), None)
    if not msg:
        return jsonify({'ok': False, 'error': 'Message not found'}), 404
    if msg.get('status') == 'sent':
        return jsonify({'ok': False, 'error': 'Cannot edit a sent message'}), 409
    data = request.json or {}
    for field in ('content', 'scheduled_at', 'recipient_phone', 'recipient_name'):
        if field in data:
            msg[field] = data[field]
    msg['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_queue(q)
    return jsonify({'ok': True})

@app.route('/api/promo/sender/pop_next', methods=['POST'])
@require_auth
def pop_next():
    q = load_queue()
    now = datetime.now(timezone.utc).isoformat()
    queued = [m for m in q if m.get('status') == 'queued']
    if not queued:
        return jsonify({'ok': False, 'message': 'Queue is empty'})
    timed   = sorted([m for m in queued if m.get('scheduled_at') and m['scheduled_at'] <= now], key=lambda x: x['scheduled_at'])
    untimed = sorted([m for m in queued if not m.get('scheduled_at')], key=lambda x: x.get('created_at', ''))
    target  = timed[0] if timed else (untimed[0] if untimed else None)
    if not target:
        return jsonify({'ok': False, 'message': 'No messages due for dispatch'})
    device_id = get_device_id()
    if not device_id:
        return jsonify({'ok': False, 'message': 'GoWA: no device registered - scan QR at :3000'})
    result = send_via_gowa(target, device_id)
    for m in q:
        if m.get('id') == target.get('id'):
            m['status'] = 'sent' if result['ok'] else 'failed'
            m['sent_at'] = now
            if not result['ok']: m['error'] = result.get('error')
    save_queue(q)
    return jsonify(result)

@app.route('/queue/<msg_id>/send_now', methods=['POST'])
@require_auth
def send_now(msg_id):
    q = load_queue()
    target = next((m for m in q if m.get('id') == msg_id), None)
    if not target:
        return jsonify({'ok': False, 'error': 'Message not found'}), 404
    if target.get('status') == 'sent':
        return jsonify({'ok': False, 'error': 'Already sent'}), 400
    device_id = get_device_id()
    if not device_id:
        return jsonify({'ok': False, 'error': 'GoWA: no device connected'}), 503
    result = send_via_gowa(target, device_id)
    now = datetime.now(timezone.utc).isoformat()
    for m in q:
        if m.get('id') == msg_id:
            m['status'] = 'sent' if result['ok'] else 'failed'
            m['sent_at'] = now
            if not result['ok']: m['error'] = result.get('error')
    save_queue(q)
    return jsonify(result)

@app.route('/queue/bulk-delete', methods=['POST'])
@require_auth
def bulk_delete():
    ids = set(request.get_json(silent=True) or [])
    if not ids:
        return jsonify({'ok': False, 'error': 'ids required'}), 400
    q = load_queue()
    before = len(q)
    q = [m for m in q if m.get('id') not in ids]
    save_queue(q)
    return jsonify({'ok': True, 'deleted': before - len(q)})


@app.route('/queue/delete-sent', methods=['POST'])
@require_auth
def delete_all_sent():
    q = load_queue()
    before = len(q)
    q = [m for m in q if m.get('status') != 'sent']
    save_queue(q)
    return jsonify({'ok': True, 'deleted': before - len(q)})


@app.route('/queue/delete-failed', methods=['POST'])
@require_auth
def delete_all_failed():
    q = load_queue()
    before = len(q)
    q = [m for m in q if m.get('status') != 'failed']
    save_queue(q)
    return jsonify({'ok': True, 'deleted': before - len(q)})


@app.route('/queue/<msg_id>/delete', methods=['POST'])
@require_auth
def delete_message(msg_id):
    q = load_queue()
    original_len = len(q)
    q = [m for m in q if m.get('id') != msg_id]
    if len(q) == original_len:
        return jsonify({'ok': False, 'error': 'Message not found'}), 404
    save_queue(q)
    return jsonify({'ok': True})

@app.route('/queue/<msg_id>/preview', methods=['POST'])
@require_auth
def preview_message(msg_id):
    q = load_queue()
    target = next((m for m in q if m.get('id') == msg_id), None)
    if not target:
        return jsonify({'ok': False, 'error': 'Message not found'}), 404
    device_id = get_device_id()
    if not device_id:
        return jsonify({'ok': False, 'error': 'GoWA: no device connected'}), 503
    preview_msg = dict(target)
    preview_msg['recipient_phone'] = '27822909093'
    result = send_via_gowa(preview_msg, device_id)
    return jsonify(result)

@app.route('/gowa/reconnect', methods=['POST'])
@require_auth
def trigger_reconnect():
    """Manually trigger a GoWA reconnect attempt. Clears needs_login flag if successful."""
    _ensure_device()
    state, detail = _get_device_state()
    if state == 'logged_in':
        return jsonify({'ok': True, 'status': 'already_connected'})
    if state in ('disconnected', 'needs_login'):
        ok = _attempt_reconnect()
        if ok:
            flag = '/opt/indaba-sender/data/gowa_needs_login.flag'
            if os.path.exists(flag):
                os.remove(flag)
            _gowa_state['status'] = 'connected'
            return jsonify({'ok': True, 'status': 'reconnected'})
        return jsonify({'ok': False, 'status': 'needs_qr',
                        'message': 'Session expired — open http://13.218.60.13:3000 and scan QR'})
    return jsonify({'ok': False, 'status': state, 'detail': detail})

def _verify_gowa_signature(raw_body: bytes, sig_header: str) -> bool:
    """GoWA v8.3+ sends X-Hub-Signature-256: sha256=HMAC-SHA256(secret, body)."""
    if not WEBHOOK_SECRET:
        return True
    if not sig_header.startswith('sha256='):
        return False
    expected = hmac.new(WEBHOOK_SECRET.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
    received = sig_header[len('sha256='):]
    return hmac.compare_digest(expected, received)


@app.route('/gowa/webhook', methods=['POST'])
def gowa_webhook():
    """Receive incoming-message events from GoWA v8.3+ and store them in inbound.json."""
    raw_body = request.get_data()
    sig      = request.headers.get('X-Hub-Signature-256', '')
    if not _verify_gowa_signature(raw_body, sig):
        log.warning('Webhook HMAC rejected from %s — sig=%s', request.remote_addr, sig[:30])
        return jsonify({'ok': False, 'error': 'Forbidden'}), 403

    payload = request.get_json(silent=True) or {}
    msg = _extract_inbound(payload)
    if msg is None:
        # Not an inbound text message — acknowledge and ignore
        return jsonify({'ok': True, 'skipped': True})

    inbound = load_inbound()
    inbound.append(msg)
    save_inbound(inbound)
    return jsonify({'ok': True, 'id': msg['id']})


@app.route('/inbound', methods=['GET'])
@require_auth
def list_inbound():
    """Return all unconsumed inbound messages for Indaba to process."""
    msgs = [m for m in load_inbound() if not m.get('consumed')]
    # Strip raw_event from response to keep payload small
    return jsonify([{k: v for k, v in m.items() if k != 'raw_event'} for m in msgs])


@app.route('/inbound/consume', methods=['POST'])
@require_auth
def consume_inbound():
    """Mark inbound message IDs as consumed so they are not returned again."""
    ids = set(request.get_json(silent=True) or [])
    if not ids:
        return jsonify({'ok': False, 'error': 'ids required'}), 400
    inbound = load_inbound()
    count = 0
    for m in inbound:
        if m['id'] in ids:
            m['consumed'] = True
            count += 1
    save_inbound(inbound)
    return jsonify({'ok': True, 'consumed': count})


@app.route('/health', methods=['GET'])
def health():
    q = load_queue()
    gowa_status = _gowa_state.get('status', 'unknown')
    needs_login = os.path.exists('/opt/indaba-sender/data/gowa_needs_login.flag')
    return jsonify({
        'ok':           True,
        'queued':       len([m for m in q if m.get('status') == 'queued']),
        'gowa_status':  gowa_status,
        'gowa_device':  GOWA_DEVICE_NAME if gowa_status == 'connected' else 'not connected',
        'needs_qr':     needs_login,
    })

@app.route('/status', methods=['GET'])
@require_auth
def status_page():
    q = load_queue()
    device_id = get_device_id()
    rows = ""
    for m in reversed(q):
        status = m.get('status', 'unknown')
        colour = {'queued': '#f0ad4e', 'sent': '#5cb85c', 'failed': '#d9534f'}.get(status, '#aaa')
        sched_raw = m.get('scheduled_at') or ''
        scheduled_display = fmt_sast(sched_raw) if sched_raw else 'FIFO'
        ts_raw = m.get('sent_at') or m.get('cloud_queued_at') or ''
        ts_display = fmt_sast(ts_raw)
        raw_content = m.get('content') or ''
        content_preview = raw_content[:80].replace('<', '&lt;')
        if len(raw_content) > 80: content_preview += '\u2026'
        media = '\U0001f5bc' if m.get('media_url') else '\U0001f4ac'
        msg_id = m.get('id', '')
        # Checkbox only for queued/failed messages
        chk = ''
        if status in ('queued', 'failed'):
            chk = f'<input type="checkbox" class="row-chk" data-id="{msg_id}" onchange="updateBulkBar()">'
        btn = ''
        if status in ('queued', 'failed'):
            btn = (f'<button class="sbtn" data-id="{msg_id}">Send now</button>'
                   f' <button class="pbtn" data-id="{msg_id}">Preview</button>'
                   f' <button class="dbtn" data-id="{msg_id}">Delete</button>')
        # Scheduled cell: click to reschedule if queued/failed
        if status in ('queued', 'failed') and sched_raw:
            # Convert ISO to datetime-local value (strip tz, keep YYYY-MM-DDTHH:MM)
            try:
                dt_utc = datetime.fromisoformat(sched_raw.replace('Z', '+00:00'))
                dt_sast = dt_utc.astimezone(SAST)
                dt_local = dt_sast.strftime('%Y-%m-%dT%H:%M')
            except Exception:
                dt_local = sched_raw[:16]
            sched_cell = (f'<span class="sched-display" data-id="{msg_id}" data-iso="{sched_raw}" '
                          f'title="Click to reschedule" style="cursor:pointer;text-decoration:underline dotted;">'
                          f'{scheduled_display}</span>'
                          f'<span class="sched-edit" data-id="{msg_id}" style="display:none;">'
                          f'<input type="datetime-local" class="sched-input" data-id="{msg_id}" value="{dt_local}" '
                          f'style="background:#1a1a2e;color:#eee;border:1px solid #555;border-radius:4px;padding:2px 6px;font-size:0.82em;">'
                          f'<button class="rbtn" data-id="{msg_id}" style="margin-left:4px;">Save</button>'
                          f'<button class="rcancelbtn" data-id="{msg_id}" style="margin-left:2px;">✕</button>'
                          f'</span>')
        elif status in ('queued', 'failed') and not sched_raw:
            sched_cell = (f'<span class="sched-display" data-id="{msg_id}" data-iso="" '
                          f'title="Click to set schedule" style="cursor:pointer;text-decoration:underline dotted;color:#888;">'
                          f'FIFO</span>'
                          f'<span class="sched-edit" data-id="{msg_id}" style="display:none;">'
                          f'<input type="datetime-local" class="sched-input" data-id="{msg_id}" value="" '
                          f'style="background:#1a1a2e;color:#eee;border:1px solid #555;border-radius:4px;padding:2px 6px;font-size:0.82em;">'
                          f'<button class="rbtn" data-id="{msg_id}" style="margin-left:4px;">Save</button>'
                          f'<button class="rcancelbtn" data-id="{msg_id}" style="margin-left:2px;">✕</button>'
                          f'</span>')
        else:
            sched_cell = scheduled_display
        # Column order: checkbox | icon | status | recipient | content | scheduled | error | actions | timestamp
        rows += (
            f'<tr>'
            f'<td style="width:30px;text-align:center;">{chk}</td>'
            f'<td>{media}</td>'
            f'<td data-val="{status}" style="color:{colour};font-weight:bold">{status}</td>'
            f'<td data-val="{m.get("recipient_name","")}">{m.get("recipient_name","")}<br><small>{m.get("recipient_phone","")}</small></td>'
            f'<td>{content_preview}</td>'
            f'<td data-val="{sched_raw}">{sched_cell}</td>'
            f'<td data-val="{m.get("error","")}" style="color:#d9534f;font-size:0.85em">{m.get("error","")}</td>'
            f'<td>{btn}</td>'
            f'<td data-val="{ts_raw}" style="color:#666;font-size:0.82em">{ts_display}</td>'
            f'</tr>'
        )
    queued_count = len([m for m in q if m.get('status') == 'queued'])
    sent_count   = len([m for m in q if m.get('status') == 'sent'])
    failed_count = len([m for m in q if m.get('status') == 'failed'])
    ws = _gowa_state.get('status', 'unknown')
    if ws == 'connected':
        dev_label = '\u2705 Connected — ' + GOWA_DEVICE_NAME
    elif ws == 'needs_login':
        dev_label = '\u26a0\ufe0f Needs QR scan at :3000'
    elif ws == 'reconnecting':
        dev_label = '\U0001f504 Reconnecting\u2026'
    elif ws == 'error':
        dev_label = '\u274c GoWA unreachable'
    else:
        dev_label = '\U0001f4f1 Checking\u2026 (starting up)'
    empty_row = '<tr><td colspan="9" style="text-align:center;color:#666;padding:40px">Queue is empty</td></tr>'
    bulk_btns = (
        f'<div style="display:flex;gap:10px;margin-bottom:18px;flex-wrap:wrap;">'
        f'<button class="bulk-del-sent" style="background:#5cb85c;border:none;color:#fff;padding:6px 16px;border-radius:4px;cursor:pointer;font-size:0.85em;{("" if sent_count > 0 else "opacity:0.4;cursor:default;")}">&#128465; Delete all sent ({sent_count})</button>'
        f'<button class="bulk-del-failed" style="background:#d9534f;border:none;color:#fff;padding:6px 16px;border-radius:4px;cursor:pointer;font-size:0.85em;{("" if failed_count > 0 else "opacity:0.4;cursor:default;")}">&#128465; Delete all failed ({failed_count})</button>'
        f'<button id="bulk-del-selected" style="background:#c0392b;border:none;color:#fff;padding:6px 16px;border-radius:4px;cursor:pointer;font-size:0.85em;display:none;">&#128465; Delete selected (<span id="sel-count">0</span>)</button>'
        f'</div>'
    )
    JS = """
<script>
var sortCol = -1, sortAsc = true;
var autoRefreshTimer = setInterval(function(){ location.reload(); }, 120000);

function updateBulkBar() {
  var checked = document.querySelectorAll('.row-chk:checked');
  var btn = document.getElementById('bulk-del-selected');
  var cnt = document.getElementById('sel-count');
  if (checked.length > 0) {
    btn.style.display = 'inline-block';
    cnt.textContent = checked.length;
  } else {
    btn.style.display = 'none';
  }
}

function toggleAllCheckboxes(cb) {
  document.querySelectorAll('.row-chk').forEach(function(c) { c.checked = cb.checked; });
  updateBulkBar();
}

function sortTable(col) {
  var table = document.getElementById('msgtable');
  var tbody = table.querySelector('tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  if (sortCol === col) { sortAsc = !sortAsc; } else { sortCol = col; sortAsc = true; }
  rows.sort(function(a, b) {
    var tda = a.querySelectorAll('td')[col];
    var tdb = b.querySelectorAll('td')[col];
    var va = tda ? (tda.getAttribute('data-val') || tda.textContent).trim().toLowerCase() : '';
    var vb = tdb ? (tdb.getAttribute('data-val') || tdb.textContent).trim().toLowerCase() : '';
    if (va < vb) return sortAsc ? -1 : 1;
    if (va > vb) return sortAsc ? 1 : -1;
    return 0;
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
  document.querySelectorAll('th.sortable').forEach(function(th) {
    var label = th.getAttribute('data-label');
    var isActive = parseInt(th.getAttribute('data-col')) === col;
    th.innerHTML = label + (isActive ? (sortAsc ? ' &#9650;' : ' &#9660;') : '');
  });
}
document.querySelectorAll('th.sortable').forEach(function(th) {
  th.addEventListener('click', function() {
    sortTable(parseInt(this.getAttribute('data-col')));
  });
});

// Reschedule: show edit widget on click
document.querySelectorAll('.sched-display').forEach(function(el) {
  el.addEventListener('click', function() {
    var id = this.getAttribute('data-id');
    this.style.display = 'none';
    var editEl = document.querySelector('.sched-edit[data-id="' + id + '"]');
    if (editEl) editEl.style.display = 'inline';
  });
});
document.querySelectorAll('.rcancelbtn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var id = this.getAttribute('data-id');
    var editEl = document.querySelector('.sched-edit[data-id="' + id + '"]');
    if (editEl) editEl.style.display = 'none';
    var dispEl = document.querySelector('.sched-display[data-id="' + id + '"]');
    if (dispEl) dispEl.style.display = 'inline';
  });
});
document.querySelectorAll('.rbtn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var id = this.getAttribute('data-id');
    var input = document.querySelector('.sched-input[data-id="' + id + '"]');
    if (!input) return;
    var val = input.value; // YYYY-MM-DDTHH:MM in SAST
    // Convert SAST to UTC ISO string for storage
    var isoUtc = null;
    if (val) {
      // datetime-local is SAST (UTC+2), subtract 2h to get UTC
      var dt = new Date(val + ':00+02:00');
      isoUtc = dt.toISOString();
    }
    var b = this; b.disabled = true; b.textContent = 'Saving\u2026';
    clearInterval(autoRefreshTimer);
    fetch('/queue/' + id, {
      method: 'PUT',
      headers: {'Authorization': 'Basic ' + btoa('admin:admin'), 'Content-Type': 'application/json'},
      body: JSON.stringify({scheduled_at: isoUtc})
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.ok) { location.reload(); }
      else { alert('Error: ' + (d.error || JSON.stringify(d))); b.disabled = false; b.textContent = 'Save'; autoRefreshTimer = setInterval(function(){ location.reload(); }, 120000); }
    });
  });
});

document.querySelectorAll('.dbtn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var id = this.getAttribute('data-id');
    if (!confirm('Delete this message from the queue?')) return;
    var b = this; b.disabled = true; b.textContent = '\u2026';
    fetch('/queue/' + id + '/delete', {method: 'POST', headers: {'Authorization': 'Basic ' + btoa('admin:admin')}})
    .then(function(r) { return r.json(); })
    .then(function(d) { if (d.ok) { location.reload(); } else { alert('Error: ' + d.error); } });
  });
});
document.querySelectorAll('.pbtn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var id = this.getAttribute('data-id');
    var b = this; b.disabled = true; b.textContent = 'Sending\u2026';
    clearInterval(autoRefreshTimer);
    fetch('/queue/' + id + '/preview', {method: 'POST', headers: {'Authorization': 'Basic ' + btoa('admin:admin')}})
    .then(function(r) { return r.json(); })
    .then(function(d) {
      b.disabled = false; b.textContent = 'Preview';
      autoRefreshTimer = setInterval(function(){ location.reload(); }, 120000);
      if (d.ok) { alert('Preview sent to your WhatsApp!'); }
      else { alert('Failed: ' + (d.error || JSON.stringify(d))); }
    });
  });
});
document.querySelectorAll('.sbtn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var id = this.getAttribute('data-id');
    if (!confirm('Send this message now?')) return;
    var b = this; b.disabled = true; b.textContent = 'Sending\u2026';
    clearInterval(autoRefreshTimer);
    fetch('/queue/' + id + '/send_now', {method: 'POST', headers: {'Authorization': 'Basic ' + btoa('admin:admin')}})
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.ok) { alert('Sent!'); location.reload(); }
      else { alert('Failed: ' + (d.error || JSON.stringify(d))); location.reload(); }
    });
  });
});

var bds = document.querySelector('.bulk-del-sent');
if (bds) bds.addEventListener('click', function() {
  if (this.style.opacity === '0.4' || this.style.opacity === '0.40') return;
  if (!confirm('Delete ALL sent messages? This cannot be undone.')) return;
  var b = this; b.disabled = true; b.textContent = 'Deleting\u2026';
  fetch('/queue/delete-sent', {method: 'POST', headers: {'Authorization': 'Basic ' + btoa('admin:admin')}})
  .then(function(r) { return r.json(); })
  .then(function(d) { location.reload(); });
});
var bdf = document.querySelector('.bulk-del-failed');
if (bdf) bdf.addEventListener('click', function() {
  if (this.style.opacity === '0.4' || this.style.opacity === '0.40') return;
  if (!confirm('Delete ALL failed messages? This cannot be undone.')) return;
  var b = this; b.disabled = true; b.textContent = 'Deleting\u2026';
  fetch('/queue/delete-failed', {method: 'POST', headers: {'Authorization': 'Basic ' + btoa('admin:admin')}})
  .then(function(r) { return r.json(); })
  .then(function(d) { location.reload(); });
});

var bsel = document.getElementById('bulk-del-selected');
if (bsel) bsel.addEventListener('click', function() {
  var checked = Array.from(document.querySelectorAll('.row-chk:checked')).map(function(c) { return c.getAttribute('data-id'); });
  if (!checked.length) return;
  if (!confirm('Delete ' + checked.length + ' selected message(s)? This cannot be undone.')) return;
  var b = this; b.disabled = true; b.textContent = 'Deleting\u2026';
  fetch('/queue/bulk-delete', {
    method: 'POST',
    headers: {'Authorization': 'Basic ' + btoa('admin:admin'), 'Content-Type': 'application/json'},
    body: JSON.stringify(checked)
  })
  .then(function(r) { return r.json(); })
  .then(function(d) { location.reload(); });
});
</script>"""
    html = (
        '<!DOCTYPE html><html><head>'
        '<meta charset="utf-8">'
        '<title>Indaba Sender</title>'
        '<style>'
        'body{font-family:system-ui,sans-serif;background:#1a1a2e;color:#eee;padding:20px}'
        'h1{color:#f0ad4e;margin-bottom:4px}'
        '.meta{color:#888;margin-bottom:20px;font-size:0.9em}'
        '.pills{display:flex;gap:12px;margin-bottom:24px}'
        '.pill{padding:8px 18px;border-radius:20px;font-weight:bold;font-size:0.9em}'
        '.pq{background:#f0ad4e;color:#000}.ps{background:#5cb85c;color:#fff}'
        '.pf{background:#d9534f;color:#fff}.pd{background:#5bc0de;color:#000}'
        'table{width:100%;border-collapse:collapse;font-size:0.88em}'
        'th{text-align:left;border-bottom:1px solid #444;padding:8px 10px;color:#aaa;text-transform:uppercase;font-size:0.8em}'
        'th.sortable{cursor:pointer;user-select:none}'
        'th.sortable:hover{color:#fff}'
        'td{padding:8px 10px;border-bottom:1px solid #2a2a3e;vertical-align:top}'
        'tr:hover td{background:#252540}'
        '.sbtn{background:#f0ad4e;border:none;color:#000;padding:4px 12px;border-radius:4px;cursor:pointer;font-size:0.82em}'
        '.sbtn:hover{background:#e09a1a}.sbtn:disabled{opacity:0.5}'
        '.pbtn{background:#5bc0de;border:none;color:#000;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:0.82em;margin-left:4px}'
        '.pbtn:hover{background:#3bafd4}'
        '.dbtn{background:#d9534f;border:none;color:#fff;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:0.82em;margin-left:4px}'
        '.dbtn:hover{background:#b52b27}'
        '.rbtn{background:#27ae60;border:none;color:#fff;padding:3px 10px;border-radius:4px;cursor:pointer;font-size:0.82em}'
        '.rbtn:hover{background:#1e8449}.rbtn:disabled{opacity:0.5}'
        '.rcancelbtn{background:#555;border:none;color:#eee;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:0.82em}'
        '.rcancelbtn:hover{background:#777}'
        'input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:#f0ad4e}'
        '</style></head><body>'
        '<h1>\U0001f4ec Indaba Sender</h1>'
        f'<div class="meta">EC2 \xb7 Auto-refreshes every 2 min \xb7 {len(q)} total messages</div>'
        '<div class="pills">'
        f'<span class="pill pq">\u23f3 {queued_count} queued</span>'
        f'<span class="pill ps">\u2705 {sent_count} sent</span>'
        f'<span class="pill pf">\u274c {failed_count} failed</span>'
        f'<span class="pill pd">\U0001f4f1 {dev_label}</span>'
        '</div>'
        + bulk_btns +
        '<table id="msgtable"><thead><tr>'
        '<th style="width:30px;"><input type="checkbox" onchange="toggleAllCheckboxes(this)" title="Select all" style="width:15px;height:15px;cursor:pointer;accent-color:#f0ad4e;"></th>'
        '<th></th>'
        '<th class="sortable" data-col="2" data-label="Status">Status</th>'
        '<th class="sortable" data-col="3" data-label="Recipient">Recipient</th>'
        '<th>Content</th>'
        '<th class="sortable" data-col="5" data-label="Scheduled">Scheduled (SAST)</th>'
        '<th class="sortable" data-col="6" data-label="Error">Error</th>'
        '<th>Actions</th>'
        '<th class="sortable" data-col="8" data-label="Timestamp">Timestamp (SAST)</th>'
        '</tr></thead><tbody>'
        + (rows if rows else empty_row)
        + '</tbody></table>'
        + JS
        + '</body></html>'
    )
    return html, 200, {'Content-Type': 'text/html'}

# ── Job-match webhook ─────────────────────────────────────────────────────────

JOBS_LOG_FILE = '/opt/indaba-sender/data/jobs_log.json'
FIDEL_PHONE   = '27822909093'

def _jobs_log_append(entry):
    try:
        data = []
        if os.path.exists(JOBS_LOG_FILE):
            with open(JOBS_LOG_FILE) as f:
                data = json.load(f)
        data.append(entry)
        data = data[-500:]  # keep last 500
        tmp = JOBS_LOG_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, JOBS_LOG_FILE)
    except Exception as e:
        log.error('jobs_log_append error: %s', e)

def _evaluate_job_fit(text):
    """
    Call Deepseek to evaluate if a job post is a fit for Fidel Namisi.
    Returns (is_fit: bool, score: int, summary: str, reason: str)
    """
    api_key = os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('OPENAI_API_KEY')
    if not api_key:
        log.warning('DEEPSEEK_API_KEY not set — skipping AI evaluation')
        return False, 0, text[:100], 'No API key configured'
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url='https://api.deepseek.com')
        resp = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{
                'role': 'system',
                'content': (
                    'You evaluate job posts for Fidel Namisi, a professional author of African fantasy '
                    'fiction based in South Africa. He writes novels and series published via Patreon '
                    'and WhatsApp, with deep expertise in African mythology, storytelling, and '
                    'worldbuilding. He also runs creative writing workshops.\n\n'
                    'GOOD FIT (score 7-10): creative/fiction writing, editorial work, content creation, '
                    'storytelling/narrative design, author events, script/screenwriting, publishing '
                    'deals, writing workshops, African literature/culture projects, copywriting for '
                    'creative industries, brand storytelling.\n\n'
                    'POOR FIT (score 1-4): software/IT, finance/accounting, medical/health, '
                    'engineering, generic sales/customer service, manufacturing, logistics.\n\n'
                    'Respond ONLY with valid JSON: '
                    '{"score": <1-10>, "summary": "<one line job title and org>", '
                    '"reason": "<one sentence why fit or not>"}'
                )
            }, {
                'role': 'user',
                'content': f'Job post:\n\n{text[:3000]}'
            }],
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        result = json.loads(raw)
        score   = int(result.get('score', 0))
        summary = result.get('summary', '')
        reason  = result.get('reason', '')
        return score >= 7, score, summary, reason
    except Exception as e:
        log.error('_evaluate_job_fit error: %s', e)
        return False, 0, '', str(e)


@app.route('/jobwebhook', methods=['POST'])
def job_webhook():
    """
    Receive a job post forwarded by indaba-jobs-webhook.
    Evaluate fit with Deepseek. If score >= 7, send Fidel a WA DM immediately.
    """
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'ok': False, 'error': 'No text body'}), 400

    log.info('Job post received (%d chars): %.80s…', len(text), text)

    is_fit, score, summary, reason = _evaluate_job_fit(text)

    entry = {
        'id':          str(uuid.uuid4()),
        'received_at': datetime.now(timezone.utc).isoformat(),
        'score':       score,
        'is_fit':      is_fit,
        'summary':     summary,
        'reason':      reason,
        'text_preview': text[:300],
    }
    _jobs_log_append(entry)

    if is_fit:
        wa_body = (
            f'\U0001f3af *Job Alert* (score {score}/10)\n\n'
            f'*{summary}*\n\n'
            f'_{reason}_\n\n'
            f'---\n{text[:1000]}'
        )
        device_id = get_device_id()
        if device_id:
            result = send_via_gowa(
                {'recipient_phone': FIDEL_PHONE, 'content': wa_body},
                device_id
            )
            log.info('Job matched (score=%d) — WA DM result: %s', score, result)
            return jsonify({'ok': True, 'matched': True, 'score': score, 'sent': result.get('ok')})
        else:
            # GoWA down — queue it so cron delivers it
            job_id = str(uuid.uuid4())
            q = load_queue()
            q.append({
                'id':               job_id,
                'recipient_phone':  FIDEL_PHONE,
                'recipient_name':   'Fidel (Job Alert)',
                'content':          wa_body,
                'status':           'queued',
                'cloud_queued_at':  datetime.now(timezone.utc).isoformat(),
                'source':           'jobs_webhook',
            })
            save_queue(q)
            log.info('Job matched (score=%d) — GoWA down, queued id=%s', score, job_id)
            return jsonify({'ok': True, 'matched': True, 'score': score, 'queued_id': job_id})
    else:
        log.info('Job skipped (score=%d): %s', score, summary)
        return jsonify({'ok': True, 'matched': False, 'score': score, 'summary': summary})


@app.route('/jobs/log', methods=['GET'])
@require_auth
def jobs_log():
    """Return the last N job evaluations."""
    n = int(request.args.get('n', 50))
    data = []
    if os.path.exists(JOBS_LOG_FILE):
        with open(JOBS_LOG_FILE) as f:
            data = json.load(f)
    return jsonify(data[-n:])


if __name__ == '__main__':
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    # Start GoWA watchdog — runs in background, auto-reconnects on drops
    t = threading.Thread(target=_watchdog_loop, daemon=True, name='gowa-watchdog')
    t.start()
    app.run(host='0.0.0.0', port=5555)
