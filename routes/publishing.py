"""
Publishing Central routes — WA queue for modules.
"""
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json
from utils.constants import (
    PROMO_MESSAGES_FILE, PROMO_SETTINGS_FILE, DEFAULT_PROMO_SETTINGS
)

bp = Blueprint('publishing', __name__)


@bp.route('/api/publishing/modules/<module_id>/queue_wa', methods=['POST'])
def queue_publishing_wa(module_id):
    data         = request.get_json()
    recipient    = data.get('recipient')
    content      = data.get('content', '').strip()
    scheduled_at = data.get('scheduled_at')

    if not recipient or recipient not in ('vip_group', 'channel'):
        return jsonify({'error': 'recipient must be "vip_group" or "channel"'}), 400
    if not content:
        return jsonify({'error': 'content is required'}), 400

    pipeline = read_json('content_pipeline.json') or []
    module   = next((e for e in pipeline if e['id'] == module_id), None)
    if not module:
        return jsonify({'error': 'Module not found'}), 404

    settings      = read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS
    wa_recipients = settings.get('publishing_wa_recipients', {})

    if recipient == 'vip_group':
        phone = wa_recipients.get('vip_group_id', '').strip()
        label = wa_recipients.get('vip_group_label', 'VIP WhatsApp Group')
    else:
        phone = wa_recipients.get('channel_id', '').strip()
        label = wa_recipients.get('channel_label', 'WA Channel')

    if not phone:
        key = 'VIP Group' if recipient == 'vip_group' else 'WA Channel'
        return jsonify({'error': f'Configure the {key} ID in Settings → WhatsApp Recipients first'}), 400

    now     = datetime.utcnow().isoformat() + "Z"
    msg_id  = str(uuid.uuid4())
    new_msg = {
        "id":               msg_id,
        "recipient_phone":  phone,
        "recipient_name":   label,
        "content":          content,
        "status":           "queued",
        "source":           "publishing_central",
        "module_id":        module_id,
        "lead_id":          None,
        "bulk_batch_id":    None,
        "scheduled_at":     scheduled_at,
        "sent_at":          None,
        "created_at":       now,
        "updated_at":       now,
    }
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msgs_data["messages"].append(new_msg)
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    return jsonify({"message_id": msg_id, "status": "queued"}), 201


# Backwards-compat alias
@bp.route('/api/publishing/chapters/<module_id>/queue_wa', methods=['POST'])
def queue_publishing_wa_compat(module_id):
    return queue_publishing_wa(module_id)
