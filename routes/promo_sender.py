"""
Promo sender routes — queue processing, EC2 delivery, reconcile.
"""
import glob
import json
import os
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json, DATA_DIR
from utils.constants import PROMO_MESSAGES_FILE, PROMO_PROVERBS_FILE, PROMO_LEADS_FILE
from services.distribution_service import (
    write_cowork_job, mark_proverb_sent
)

bp = Blueprint('promo_sender', __name__)


@bp.route('/api/promo/sender/pop_next', methods=['POST'])
def pop_next_message():
    import requests as _req
    cloud_url = os.environ.get('EC2_SENDER_URL', '').rstrip('/')
    if not cloud_url:
        return jsonify({"ok": False, "error": "EC2_SENDER_URL not configured"}), 503
    try:
        r = _req.post(f'{cloud_url}/api/promo/sender/pop_next',
                      auth=('admin', 'admin'), timeout=30)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@bp.route('/api/promo/broadcast_post/send_next', methods=['POST'])
def legacy_send_next():
    """Backward-compat alias for pop_next."""
    from flask import current_app
    with current_app.test_request_context():
        pass
    return pop_next_message()


@bp.route('/api/promo/sender/process_queue', methods=['POST'])
def process_promo_queue():
    data       = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now        = datetime.utcnow().isoformat() + "Z"
    dispatched = 0
    failed     = 0

    for m in data["messages"]:
        if m.get("status") == "queued":
            sched = m.get("scheduled_at")
            if not sched or sched <= now:
                if write_cowork_job(m):
                    m["status"]     = "dispatched"
                    m["updated_at"] = now
                    dispatched += 1
                else:
                    m["status"]     = "failed"
                    m["updated_at"] = now
                    failed += 1

    write_json(PROMO_MESSAGES_FILE, data)
    return jsonify({
        "dispatched":  dispatched,
        "failed":      failed,
        "instruction": "Trigger Cowork with: Send WhatsApps from Indaba",
    })


@bp.route('/api/promo/sender/reconcile', methods=['POST'])
def reconcile_promo_results():
    results_dir = os.path.join(DATA_DIR, 'cowork_results')
    if not os.path.exists(results_dir):
        return jsonify({"reconciled": 0, "message": "No results found."})

    files = glob.glob(os.path.join(results_dir, "*.json"))
    if not files:
        return jsonify({"reconciled": 0, "message": "No results found."})

    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    leads_data    = read_json(PROMO_LEADS_FILE)    or {"leads": []}
    reconciled = sent_count = failed_count = 0
    now = datetime.utcnow().isoformat() + "Z"

    for f_path in files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                res = json.load(f)
            msg_id = res.get("message_id")
            status = res.get("status")
            msg = next((m for m in messages_data["messages"] if m["id"] == msg_id), None)
            if msg:
                if status == "sent":
                    msg["status"]     = "sent"
                    msg["sent_at"]    = res.get("sent_at", now)
                    msg["updated_at"] = now
                    sent_count += 1
                    lead_id = msg.get("lead_id")
                    if lead_id:
                        lead = next((l for l in leads_data["leads"] if l["id"] == lead_id), None)
                        if lead:
                            lead.setdefault("communication_log", []).append({
                                "id":         str(uuid.uuid4()),
                                "timestamp":  now,
                                "direction":  "outbound",
                                "channel":    "whatsapp",
                                "message":    msg["content"],
                                "message_id": msg["id"],
                            })
                elif status == "failed":
                    msg["status"]     = "failed"
                    msg["updated_at"] = now
                    failed_count += 1
                reconciled += 1
            os.remove(f_path)
        except Exception as e:
            print(f"Error processing result file {f_path}: {e}")

    if reconciled > 0:
        write_json(PROMO_MESSAGES_FILE, messages_data)
        write_json(PROMO_LEADS_FILE, leads_data)

    return jsonify({"reconciled": reconciled, "sent": sent_count, "failed": failed_count})


@bp.route('/api/promo/sender/send_now', methods=['POST'])
def promo_send_now():
    data = request.json
    if not data or 'message_id' not in data:
        return jsonify({"error": "message_id missing"}), 400

    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msg_id        = data['message_id']
    msg = next((m for m in messages_data["messages"] if m["id"] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    if msg.get("status") != "queued":
        return jsonify({"error": "Only queued messages can be dispatched"}), 409

    now = datetime.utcnow().isoformat() + "Z"
    if write_cowork_job(msg):
        msg["status"]     = "dispatched"
        msg["updated_at"] = now
        write_json(PROMO_MESSAGES_FILE, messages_data)
        return jsonify({"ok": True, "instruction": "Trigger Cowork with: Send WhatsApps from Indaba"})
    else:
        msg["status"]     = "failed"
        msg["updated_at"] = now
        write_json(PROMO_MESSAGES_FILE, messages_data)
        return jsonify({"ok": False, "error": "Failed to write job file"})


@bp.route('/api/promo/messages/bulk_send_now', methods=['POST'])
def bulk_send_now():
    import requests as _req
    data = request.json
    ids  = data.get('ids', [])
    if not ids:
        return jsonify({"error": "No IDs provided"}), 400

    cloud_url = os.environ.get('EC2_SENDER_URL', '').rstrip('/')
    if not cloud_url:
        return jsonify({"error": "EC2_SENDER_URL not configured"}), 503

    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    sent_count    = 0
    errors        = []
    now           = datetime.utcnow().isoformat() + "Z"

    for mid in ids:
        msg = next((m for m in messages_data["messages"] if m["id"] == mid), None)
        if not msg or msg.get("status") == "sent":
            continue
        try:
            r   = _req.post(f'{cloud_url}/queue/{mid}/send_now',
                            auth=('admin', 'admin'), timeout=30)
            res = r.json()
        except Exception as e:
            errors.append(f"Msg {mid}: {str(e)}")
            continue

        if res.get('ok'):
            msg["status"]     = "sent"
            msg["sent_at"]    = now
            msg["updated_at"] = now
            sent_count += 1
            if msg.get('proverb_id'):
                mark_proverb_sent(msg['proverb_id'], 'sent', now)
        else:
            errors.append(f"Msg {mid}: {res.get('error', 'Unknown error')}")

    write_json(PROMO_MESSAGES_FILE, messages_data)
    return jsonify({"ok": True, "sent": sent_count, "errors": errors})


@bp.route('/api/promo/message/<message_id>', methods=['PUT'])
def update_message_status(message_id):
    data     = request.get_json() or {}
    status   = data.get('status')
    allowed  = ('sent', 'failed', 'queued')
    if status not in allowed:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(allowed)}"}), 400

    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    message = next((m for m in msgs_data["messages"] if m['id'] == message_id), None)
    if not message:
        return jsonify({"error": "Message not found"}), 404

    now = datetime.utcnow().isoformat() + "Z"
    message['status']     = status
    message['updated_at'] = now

    if status == 'sent':
        message['sent_at'] = now
        message.pop('error', None)
    elif status == 'failed':
        message['error'] = data.get('error', 'Unknown error')
        message.pop('sent_at', None)
    elif status == 'queued':
        message.pop('sent_at', None)
        message.pop('error', None)

    write_json(PROMO_MESSAGES_FILE, msgs_data)

    if message.get('proverb_id'):
        p_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
        for p in p_data["proverbs"]:
            if p["id"] == message["proverb_id"]:
                p["queue_status"] = status
                p["updated_at"]   = now
                if status == 'sent':
                    p["sent_at"] = now
                elif status == 'failed':
                    p.pop('sent_at', None)
                break
        write_json(PROMO_PROVERBS_FILE, p_data)

    return jsonify({"ok": True, "message_id": message_id, "new_status": status})


@bp.route('/api/promo/messages/<msg_id>/extension_result', methods=['POST'])
def extension_send_result(msg_id):
    data    = request.get_json()
    success = data.get('success', False)
    reason  = data.get('reason')

    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msg = next((m for m in msgs_data["messages"] if m["id"] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404

    now = datetime.utcnow().isoformat() + "Z"
    if success:
        msg["status"]  = "sent"
        msg["sent_at"] = now
    else:
        msg["status"] = "failed"
        msg["error"]  = reason or "Extension reported failure"
    msg["updated_at"] = now
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    return jsonify({"ok": True, "status": msg["status"]})
