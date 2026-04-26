"""
Promo messages routes — outbox CRUD, bulk, single send, message maker.
"""
import os
import uuid
import requests as _req
from datetime import datetime

from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json
from utils.constants import (
    PROMO_MESSAGES_FILE, PROMO_CONTACTS_FILE, PROMO_LEADS_FILE,
    PROMO_SETTINGS_FILE, DEFAULT_PROMO_SETTINGS,
    MESSAGE_MAKER_SYSTEM_PROMPT
)
from services.ai_service import call_ai
from services.distribution_service import write_cowork_job, _ec2_delete, _ec2_update

bp = Blueprint('promo_messages', __name__)


@bp.route('/api/promo/messages', methods=['GET'])
def list_promo_messages():
    status = request.args.get('status')
    limit  = int(request.args.get('limit', 50))
    data   = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msgs   = data.get("messages", [])
    if status:
        msgs = [m for m in msgs if m.get('status') == status]
    msgs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify({"messages": msgs[:limit]})


@bp.route('/api/promo/messages/<msg_id>', methods=['GET'])
def get_promo_message(msg_id):
    data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msg  = next((m for m in data.get("messages", []) if m['id'] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    return jsonify(msg)


@bp.route('/api/promo/messages/<msg_id>', methods=['PUT'])
def update_promo_message(msg_id):
    data      = request.get_json() or {}
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msg = next((m for m in msgs_data.get("messages", []) if m['id'] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404

    if msg.get('status') not in ['queued', 'failed', 'overdue']:
        return jsonify({"error": f"Cannot edit message with status: {msg.get('status')}"}), 409

    updated_fields = {}
    for field in ('content', 'scheduled_at', 'recipient_phone', 'recipient_name'):
        if field in data:
            msg[field] = data[field]
            updated_fields[field] = data[field]
    msg['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    ec2_ok = _ec2_update(msg_id, updated_fields)
    return jsonify({**msg, "ec2_synced": ec2_ok})


@bp.route('/api/promo/messages/<msg_id>', methods=['DELETE'])
def delete_promo_message(msg_id):
    data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msgs = data.get("messages", [])
    msg  = next((m for m in msgs if m['id'] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    if msg.get('status') not in ['queued', 'overdue']:
        return jsonify({"error": f"Cannot delete message with status: {msg.get('status')}"}), 409
    data["messages"] = [m for m in msgs if m['id'] != msg_id]
    write_json(PROMO_MESSAGES_FILE, data)
    ec2_ok = _ec2_delete(msg_id)
    return jsonify({"ok": True, "ec2_synced": ec2_ok})


@bp.route('/api/promo/messages/<msg_id>/reschedule', methods=['POST'])
def reschedule_promo_message(msg_id):
    data      = request.get_json()
    new_time  = data.get('scheduled_at')
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msg = next((m for m in msgs_data.get("messages", []) if m['id'] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    if msg.get('status') == 'sent':
        return jsonify({"error": "Cannot reschedule a sent message"}), 409
    msg['scheduled_at'] = new_time
    msg['status']       = 'queued'
    msg['updated_at']   = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    ec2_ok = _ec2_update(msg_id, {'scheduled_at': new_time})
    return jsonify({**msg, "ec2_synced": ec2_ok})


@bp.route('/api/promo/messages/bulk', methods=['POST'])
def create_bulk_messages():
    data         = request.get_json()
    tag          = data.get('tag')
    content      = data.get('content', '')
    scheduled_at = data.get('scheduled_at')

    if not tag or not content:
        return jsonify({"error": "tag and content are required"}), 400

    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    tag_lower     = tag.lower()
    targets       = [
        c for c in contacts_data.get("contacts", [])
        if any(t.lower() == tag_lower for t in c.get('tags', []))
    ]
    if not targets:
        return jsonify({"error": f"No contacts found with tag: {tag}"}), 404

    batch_id  = str(uuid.uuid4())
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now       = datetime.utcnow().isoformat() + "Z"
    created   = []

    for c in targets:
        msg_content = content.replace("{name}", c['name'])
        new_msg = {
            "id":               str(uuid.uuid4()),
            "recipient_phone":  c['phone'],
            "recipient_name":   c['name'],
            "content":          msg_content,
            "status":           "queued",
            "source":           data.get('source', 'manual'),
            "bulk_batch_id":    batch_id,
            "scheduled_at":     scheduled_at,
            "created_at":       now,
            "updated_at":       now,
        }
        msgs_data["messages"].append(new_msg)
        created.append({"name": c['name'], "phone": c['phone']})

    write_json(PROMO_MESSAGES_FILE, msgs_data)
    return jsonify({"batch_id": batch_id, "message_count": len(created), "contacts": created})


@bp.route('/api/promo/messages/bulk/<batch_id>', methods=['GET'])
def get_bulk_batch(batch_id):
    data       = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    batch_msgs = [m for m in data.get("messages", []) if m.get('bulk_batch_id') == batch_id]
    return jsonify({"messages": batch_msgs})


@bp.route('/api/promo/messages/single', methods=['POST'])
def send_single_message():
    data         = request.get_json()
    phone        = data.get('recipient_phone')
    name         = data.get('recipient_name', 'Contact')
    content      = data.get('content')
    scheduled_at = data.get('scheduled_at')
    lead_id      = data.get('lead_id')

    if not phone or not content:
        return jsonify({"error": "recipient_phone and content are required"}), 400

    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now           = datetime.utcnow().isoformat() + "Z"
    msg_id        = str(uuid.uuid4())
    new_message   = {
        "id":               msg_id,
        "recipient_phone":  phone,
        "recipient_name":   name,
        "content":          content,
        "status":           "queued",
        "source":           "manual_single",
        "source_ref":       {"lead_id": lead_id} if lead_id else {},
        "scheduled_at":     scheduled_at,
        "created_at":       now,
        "updated_at":       now,
    }

    if not scheduled_at:
        if write_cowork_job(new_message):
            new_message['status'] = 'dispatched'
        else:
            new_message['status'] = 'failed'
            new_message['error']  = 'Failed to write job file'

    messages_data["messages"].append(new_message)
    write_json(PROMO_MESSAGES_FILE, messages_data)
    return jsonify({
        "message_id": msg_id,
        "status":     new_message['status'],
        "error":      new_message.get('error'),
    }), 201


@bp.route('/api/promo/message_maker/generate', methods=['POST'])
def generate_promo_message():
    data    = request.get_json()
    purpose = data.get('purpose', '').strip()
    if not purpose:
        return jsonify({"error": "purpose is required"}), 400

    user_prompt = f"""Purpose: {purpose}
Event Name: {data.get('event_name', '')}
Event Date: {data.get('event_date', '')}
Target Audience: {data.get('target_audience', '')}
Tone Notes: {data.get('tone_notes', '')}
Recipient Name: {data.get('recipient_name', '')}"""

    system_content = MESSAGE_MAKER_SYSTEM_PROMPT.format(purpose=purpose)
    try:
        message = call_ai("message_maker", [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": user_prompt},
        ])
        return jsonify({"message": message.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@bp.route('/api/outbox/sync', methods=['POST'])
def sync_outbox_with_ec2():
    """Pull EC2 queue state and update local statuses for messages EC2 has sent/failed."""
    cloud_url = os.environ.get('EC2_SENDER_URL', '').rstrip('/')
    if not cloud_url:
        return jsonify({"ok": False, "error": "EC2_SENDER_URL not configured"})
    try:
        r = _req.get(f'{cloud_url}/queue', auth=('admin', 'admin'), timeout=10)
        ec2_queue = r.json()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    ec2_map   = {m['id']: m for m in ec2_queue if 'id' in m}
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    updated   = 0
    now       = datetime.utcnow().isoformat() + "Z"

    for msg in msgs_data["messages"]:
        if msg.get('status') not in ('queued', 'overdue'):
            continue
        ec2_msg = ec2_map.get(msg['id'])
        if not ec2_msg:
            continue
        ec2_status = ec2_msg.get('status')
        if ec2_status in ('sent', 'failed') and ec2_status != msg.get('status'):
            msg['status']     = ec2_status
            msg['updated_at'] = now
            if ec2_msg.get('sent_at'):
                msg['sent_at'] = ec2_msg['sent_at']
            if ec2_msg.get('error'):
                msg['error'] = ec2_msg['error']
            updated += 1

    if updated:
        write_json(PROMO_MESSAGES_FILE, msgs_data)

    return jsonify({"ok": True, "updated": updated, "ec2_queue_size": len(ec2_queue)})


@bp.route('/api/promo/messages/history', methods=['DELETE'])
def clear_message_history():
    """Delete all sent messages from the outbox."""
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    before    = len(msgs_data["messages"])
    msgs_data["messages"] = [m for m in msgs_data["messages"] if m.get("status") != "sent"]
    cleared   = before - len(msgs_data["messages"])
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    return jsonify({"ok": True, "cleared": cleared})


@bp.route('/api/promo/messages/<msg_id>/preview', methods=['POST'])
def preview_message(msg_id):
    """Send a preview of this message to +27822909093 via EC2."""
    cloud_url = os.environ.get('EC2_SENDER_URL', '').rstrip('/')
    if not cloud_url:
        return jsonify({"ok": False, "error": "EC2_SENDER_URL not configured"}), 503
    try:
        r = _req.post(f'{cloud_url}/queue/{msg_id}/preview',
                      auth=('admin', 'admin'), timeout=30)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@bp.route('/api/promo/messages/inbound', methods=['POST'])
def receive_inbound_message():
    """Receive an incoming GoWA message and append it to the matching lead's communication_log."""
    data      = request.get_json() or {}
    sender    = data.get('from', '').strip()
    body      = data.get('body', '').strip()
    timestamp = data.get('timestamp', datetime.utcnow().isoformat() + "Z")

    if not sender or not body:
        return jsonify({"ok": False, "error": "from and body are required"}), 400

    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact = next((c for c in contacts_data.get("contacts", []) if c.get('phone') == sender), None)

    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    lead = None
    if contact:
        lead = next(
            (l for l in leads_data.get("leads", [])
             if l.get('contact_id') == contact['id']
             and l.get('stage') not in ('closed', 'lost')),
            None
        )

    log_entry = {
        "direction": "inbound",
        "channel":   "whatsapp",
        "body":      body,
        "timestamp": timestamp,
    }

    if lead:
        lead.setdefault('communication_log', []).append(log_entry)
        lead['updated_at'] = datetime.utcnow().isoformat() + "Z"
        write_json(PROMO_LEADS_FILE, leads_data)
        return jsonify({"ok": True, "lead_id": lead['id'], "contact_found": True})

    # Unknown sender — log without a lead
    return jsonify({"ok": True, "lead_id": None, "contact_found": False,
                    "note": f"No active lead found for {sender}"})
