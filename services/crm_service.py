"""
CRM service — contacts and deals (leads) logic.
"""
import re
import uuid
from datetime import datetime

from utils.json_store import read_json, write_json
from utils.constants import PROMO_CONTACTS_FILE, PROMO_LEADS_FILE, PROMO_MESSAGES_FILE

E164_PATTERN = re.compile(r'^\+\d{7,15}$')


# ── Contacts ─────────────────────────────────────────────────────────────────

def list_contacts():
    data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    return data.get("contacts", [])


def get_contact(contact_id):
    return next((c for c in list_contacts() if c['id'] == contact_id), None)


def create_contact(data):
    name  = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    if not name:
        raise ValueError("name is required")
    if not phone or not E164_PATTERN.match(phone):
        raise ValueError("Phone must be in E.164 format, e.g. +27821234567")

    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    if any(c.get('phone') == phone for c in contacts_data.get("contacts", [])):
        raise ValueError("A contact with this phone number already exists")

    now = datetime.utcnow().isoformat() + "Z"
    new_contact = {
        "id":         str(uuid.uuid4()),
        "name":       name,
        "phone":      phone,
        "email":      data.get('email', ''),
        "tags":       data.get('tags', []),
        "source":     data.get('source', 'manual'),
        "notes":      data.get('notes', ''),
        "created_at": now,
        "updated_at": now,
    }
    contacts_data["contacts"].append(new_contact)
    write_json(PROMO_CONTACTS_FILE, contacts_data)
    return new_contact


def update_contact(contact_id, data):
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contacts      = contacts_data.get("contacts", [])
    idx           = next((i for i, c in enumerate(contacts) if c['id'] == contact_id), None)
    if idx is None:
        return None
    contact = contacts[idx]
    if 'phone' in data:
        new_phone = data['phone'].strip()
        if not E164_PATTERN.match(new_phone):
            raise ValueError("Phone must be in E.164 format, e.g. +27821234567")
        if new_phone != contact['phone']:
            if any(c.get('phone') == new_phone for c in contacts if c['id'] != contact_id):
                raise ValueError("A contact with this phone number already exists")
        contact['phone'] = new_phone
    for field in ['name', 'email', 'tags', 'source', 'notes']:
        if field in data:
            contact[field] = data[field]
    contact['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_CONTACTS_FILE, contacts_data)
    return contact


def delete_contact(contact_id):
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contacts      = contacts_data.get("contacts", [])
    contact       = next((c for c in contacts if c['id'] == contact_id), None)
    if not contact:
        return False, None
    phone = contact['phone']
    contacts_data["contacts"] = [c for c in contacts if c['id'] != contact_id]
    write_json(PROMO_CONTACTS_FILE, contacts_data)

    # Cascade: delete associated leads
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads_data["leads"] = [l for l in leads_data.get("leads", []) if l['contact_id'] != contact_id]
    write_json(PROMO_LEADS_FILE, leads_data)

    # Update queued messages
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    changed   = False
    for m in msgs_data.get("messages", []):
        if m.get("status") == "queued" and m.get("recipient_phone") == phone:
            m["recipient_name"] = "[Deleted]"
            changed = True
    if changed:
        write_json(PROMO_MESSAGES_FILE, msgs_data)
    return True, phone


# ── Deals (Leads) ─────────────────────────────────────────────────────────────

def get_pipeline():
    data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    return data.get("leads", [])


def create_deal(data):
    contact_id   = data.get('contact_id')
    product      = data.get('product')
    product_type = data.get('product_type')
    if not all([contact_id, product, product_type]):
        raise ValueError("contact_id, product, and product_type are required")

    contact = get_contact(contact_id)
    if not contact:
        raise ValueError("Contact not found")

    from utils.constants import PROMO_SETTINGS_FILE, DEFAULT_PROMO_SETTINGS
    settings   = read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS
    max_leads  = settings.get("max_leads_per_contact", 10)
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    if len([l for l in leads_data.get("leads", []) if l['contact_id'] == contact_id]) >= max_leads:
        raise ValueError(f"Contact exceeds max leads limit ({max_leads})")

    now      = datetime.utcnow().isoformat() + "Z"
    new_deal = {
        "id":                str(uuid.uuid4()),
        "contact_id":        contact_id,
        "contact_name":      contact['name'],
        "product":           product,
        "product_type":      product_type,
        "stage":             "lead",
        "value":             data.get('value', 0),
        "entity_id":         data.get('entity_id'),
        "notes":             data.get('notes', ''),
        "communication_log": data.get('communication_log', []),
        "created_at":        now,
        "updated_at":        now,
    }
    leads_data["leads"].append(new_deal)
    write_json(PROMO_LEADS_FILE, leads_data)
    return new_deal


def update_deal_stage(lead_id, stage):
    from utils.constants import LEAD_STAGES
    if stage not in LEAD_STAGES:
        raise ValueError(f"Invalid stage. Must be one of {LEAD_STAGES}")
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    lead       = next((l for l in leads_data.get("leads", []) if l['id'] == lead_id), None)
    if not lead:
        return None
    lead['stage']      = stage
    lead['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_LEADS_FILE, leads_data)
    return lead
