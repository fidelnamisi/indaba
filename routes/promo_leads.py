"""
Promo leads routes — deals/CRM CRUD, communication log, AI suggest.
"""
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json
from utils.constants import (
    PROMO_LEADS_FILE, PROMO_CONTACTS_FILE, PROMO_MESSAGES_FILE,
    PROMO_SETTINGS_FILE, DEFAULT_PROMO_SETTINGS, LEAD_STAGES
)
from services.ai_service import call_ai

bp = Blueprint('promo_leads', __name__)


@bp.route('/api/promo/leads', methods=['GET'])
def list_promo_leads():
    contact_id = request.args.get('contact_id')
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads = leads_data.get("leads", [])
    if contact_id:
        leads = [l for l in leads if l['contact_id'] == contact_id]
    return jsonify({"leads": leads})


@bp.route('/api/promo/leads', methods=['POST'])
def create_promo_lead():
    data         = request.get_json()
    contact_id   = data.get('contact_id')
    product      = data.get('product')
    product_type = data.get('product_type')

    if not all([contact_id, product, product_type]):
        return jsonify({"error": "contact_id, product, and product_type are required"}), 400

    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact = next((c for c in contacts_data.get("contacts", []) if c['id'] == contact_id), None)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    settings  = read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS
    max_leads = settings.get("max_leads_per_contact", 10)
    leads_data    = read_json(PROMO_LEADS_FILE) or {"leads": []}
    current_leads = [l for l in leads_data.get("leads", []) if l['contact_id'] == contact_id]
    if len(current_leads) >= max_leads:
        return jsonify({"error": f"Contact exceeds max leads limit ({max_leads})"}), 409

    now      = datetime.utcnow().isoformat() + "Z"
    new_lead = {
        "id":                str(uuid.uuid4()),
        "contact_id":        contact_id,
        "contact_name":      contact['name'],
        "product":           product,
        "product_type":      product_type,
        "stage":             "lead",
        "notes":             data.get('notes', ''),
        "communication_log": [],
        "created_at":        now,
        "updated_at":        now,
    }
    leads_data["leads"].append(new_lead)
    write_json(PROMO_LEADS_FILE, leads_data)
    return jsonify(new_lead), 201


@bp.route('/api/promo/leads/<lead_id>', methods=['GET'])
def get_promo_lead(lead_id):
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    lead = next((l for l in leads_data.get("leads", []) if l['id'] == lead_id), None)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    return jsonify(lead)


@bp.route('/api/promo/leads/<lead_id>', methods=['PUT'])
def update_promo_lead(lead_id):
    data       = request.get_json()
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads      = leads_data.get("leads", [])
    lead_idx   = next((i for i, l in enumerate(leads) if l['id'] == lead_id), None)
    if lead_idx is None:
        return jsonify({"error": "Lead not found"}), 404

    lead = leads[lead_idx]
    if 'stage' in data:
        if data['stage'] not in LEAD_STAGES:
            return jsonify({"error": f"Invalid stage. Must be one of {LEAD_STAGES}"}), 400
        lead['stage'] = data['stage']
    for field in ['notes', 'product', 'product_type']:
        if field in data:
            lead[field] = data[field]
    lead['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_LEADS_FILE, leads_data)
    return jsonify(lead)


@bp.route('/api/promo/leads/<lead_id>', methods=['DELETE'])
def delete_promo_lead(lead_id):
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads      = leads_data.get("leads", [])
    if not any(l['id'] == lead_id for l in leads):
        return jsonify({"error": "Lead not found"}), 404
    leads_data["leads"] = [l for l in leads if l['id'] != lead_id]
    write_json(PROMO_LEADS_FILE, leads_data)
    return jsonify({"ok": True})


@bp.route('/api/promo/leads/<lead_id>/link_entity', methods=['POST'])
def link_deal_entity(lead_id):
    data      = request.get_json() or {}
    entity_id = data.get('entity_id')

    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    lead = next((l for l in leads_data.get("leads", []) if l['id'] == lead_id), None)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    lead['entity_id']  = entity_id
    lead['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_LEADS_FILE, leads_data)
    return jsonify(lead)


@bp.route('/api/promo/messages/<msg_id>/create_deal', methods=['POST'])
def create_deal_from_message(msg_id):
    data      = request.get_json() or {}
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msg = next((m for m in msgs_data.get("messages", []) if m['id'] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404

    product      = data.get('product', '').strip()
    product_type = data.get('product_type', 'other')
    contact_id   = data.get('contact_id')

    if not product or not contact_id:
        return jsonify({"error": "product and contact_id are required"}), 400

    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact = next((c for c in contacts_data.get("contacts", []) if c['id'] == contact_id), None)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    settings  = read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS
    max_leads = settings.get("max_leads_per_contact", 10)
    leads_data    = read_json(PROMO_LEADS_FILE) or {"leads": []}
    current_leads = [l for l in leads_data.get("leads", []) if l['contact_id'] == contact_id]
    if len(current_leads) >= max_leads:
        return jsonify({"error": f"Contact exceeds max leads limit ({max_leads})"}), 409

    now      = datetime.utcnow().isoformat() + "Z"
    new_lead = {
        "id":           str(uuid.uuid4()),
        "contact_id":   contact_id,
        "contact_name": contact['name'],
        "product":      product,
        "product_type": product_type,
        "stage":        "lead",
        "value":        data.get('value', 0),
        "entity_id":    data.get('entity_id'),
        "notes":        data.get('notes', f'Deal created from message: {msg_id}'),
        "communication_log": [{
            "id":        str(uuid.uuid4()),
            "direction": "outbound",
            "message":   msg.get('content', ''),
            "timestamp": msg.get('created_at', now),
        }],
        "created_at": now,
        "updated_at": now,
    }
    leads_data["leads"].append(new_lead)
    write_json(PROMO_LEADS_FILE, leads_data)

    msg['lead_id'] = new_lead['id']
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    return jsonify(new_lead), 201


@bp.route('/api/promo/leads/<lead_id>/log_communication', methods=['POST'])
def log_lead_communication(lead_id):
    data      = request.get_json()
    msg_text  = data.get('message')
    direction = data.get('direction')

    if not msg_text or direction not in ['inbound', 'outbound']:
        return jsonify({"error": "message and valid direction (inbound/outbound) required"}), 400

    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    lead = next((l for l in leads_data.get("leads", []) if l['id'] == lead_id), None)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    entry = {
        "id":        str(uuid.uuid4()),
        "direction": direction,
        "message":   msg_text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    lead.setdefault("communication_log", []).append(entry)
    lead["updated_at"] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_LEADS_FILE, leads_data)
    return jsonify(entry)


@bp.route('/api/promo/leads/<lead_id>/ai_suggest', methods=['POST'])
def ai_suggest_lead_message(lead_id):
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    lead = next((l for l in leads_data.get("leads", []) if l['id'] == lead_id), None)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact = next(
        (c for c in contacts_data.get("contacts", []) if c['id'] == lead['contact_id']), None
    )

    history     = lead.get("communication_log", [])[-5:]
    history_str = "\n".join([f"{m['direction']}: {m['message']}" for m in history])

    prompt = f"""Target Contact: {contact['name'] if contact else 'Prospect'}
Product: {lead['product']} (Type: {lead['product_type']})
Current Sales Stage: {lead['stage']}

Recent Communication History:
{history_str if history_str else "No prior communication logged."}

Task: Suggest the next outbound message to advance this lead to the next stage.
Keep it personal, professional, and very brief. South African context.
Return ONLY the suggested message text."""

    try:
        suggestion = call_ai("crm_assist", [{"role": "user", "content": prompt}])
        return jsonify({"suggestion": suggestion.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 502
