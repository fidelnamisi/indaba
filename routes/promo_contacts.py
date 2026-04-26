"""
Promo contacts routes.
"""
import csv
import io
import re
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json
from utils.constants import PROMO_CONTACTS_FILE, PROMO_LEADS_FILE, PROMO_MESSAGES_FILE

bp = Blueprint('promo_contacts', __name__)
E164 = re.compile(r'^\+\d{7,15}$')


@bp.route('/api/promo/contacts', methods=['GET'])
def list_promo_contacts():
    data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    return jsonify(data)


@bp.route('/api/promo/contacts', methods=['POST'])
def create_promo_contact():
    data  = request.get_json()
    name  = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    if not phone or not E164.match(phone):
        return jsonify({"error": "Phone must be in E.164 format, e.g. +27821234567"}), 400
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    if any(c.get('phone') == phone for c in contacts_data.get("contacts", [])):
        return jsonify({"error": "A contact with this phone number already exists"}), 409
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
    return jsonify(new_contact), 201


@bp.route('/api/promo/contacts/import_csv', methods=['POST'])
def import_contacts_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    if not file.filename.lower().endswith('.csv'):
        return jsonify({"error": "File must be a .csv"}), 400
    stream        = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    reader        = csv.DictReader(stream)
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    existing_phones = {c.get('phone') for c in contacts_data.get("contacts", [])}
    imported = skipped_invalid = skipped_duplicate = 0
    now = datetime.utcnow().isoformat() + "Z"
    for row in reader:
        name  = row.get('name', '').strip()
        phone = row.get('phone', '').strip()
        if not name or not phone or not E164.match(phone):
            skipped_invalid += 1
            continue
        if phone in existing_phones:
            skipped_duplicate += 1
            continue
        tags_raw = row.get('tags', '')
        tags     = [t.strip() for t in tags_raw.split(';')] if tags_raw else []
        contacts_data["contacts"].append({
            "id":         str(uuid.uuid4()),
            "name":       name,
            "phone":      phone,
            "email":      row.get('email', ''),
            "tags":       tags,
            "source":     "csv",
            "notes":      "",
            "created_at": now,
            "updated_at": now,
        })
        existing_phones.add(phone)
        imported += 1
    if imported > 0:
        write_json(PROMO_CONTACTS_FILE, contacts_data)
    return jsonify({"imported": imported, "skipped_invalid": skipped_invalid,
                    "skipped_duplicate": skipped_duplicate})


@bp.route('/api/promo/contacts/<contact_id>', methods=['GET'])
def get_promo_contact(contact_id):
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact       = next((c for c in contacts_data.get("contacts", []) if c['id'] == contact_id), None)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
    leads_data     = read_json(PROMO_LEADS_FILE) or {"leads": []}
    contact_leads  = [l for l in leads_data.get("leads", []) if l['contact_id'] == contact_id]
    return jsonify({"contact": contact, "leads": contact_leads})


@bp.route('/api/promo/contacts/<contact_id>', methods=['PUT'])
def update_promo_contact(contact_id):
    data          = request.get_json()
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contacts      = contacts_data.get("contacts", [])
    idx           = next((i for i, c in enumerate(contacts) if c['id'] == contact_id), None)
    if idx is None:
        return jsonify({"error": "Contact not found"}), 404
    contact = contacts[idx]
    if 'phone' in data:
        new_phone = data['phone'].strip()
        if not E164.match(new_phone):
            return jsonify({"error": "Phone must be in E.164 format, e.g. +27821234567"}), 400
        if new_phone != contact['phone']:
            if any(c.get('phone') == new_phone for c in contacts if c['id'] != contact_id):
                return jsonify({"error": "A contact with this phone number already exists"}), 409
        contact['phone'] = new_phone
    for field in ['name', 'email', 'tags', 'source', 'notes']:
        if field in data:
            contact[field] = data[field]
    contact['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_CONTACTS_FILE, contacts_data)
    return jsonify(contact)


@bp.route('/api/promo/contacts/<contact_id>', methods=['DELETE'])
def delete_promo_contact(contact_id):
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contacts      = contacts_data.get("contacts", [])
    contact       = next((c for c in contacts if c['id'] == contact_id), None)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
    phone = contact['phone']
    contacts_data["contacts"] = [c for c in contacts if c['id'] != contact_id]
    write_json(PROMO_CONTACTS_FILE, contacts_data)
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads_data["leads"] = [l for l in leads_data.get("leads", []) if l['contact_id'] != contact_id]
    write_json(PROMO_LEADS_FILE, leads_data)
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    changed   = False
    for m in msgs_data.get("messages", []):
        if m.get("status") == "queued" and m.get("recipient_phone") == phone:
            m["recipient_name"] = "[Deleted]"
            changed = True
    if changed:
        write_json(PROMO_MESSAGES_FILE, msgs_data)
    return jsonify({"ok": True})


@bp.route('/api/promo/contacts/<contact_id>/tags', methods=['POST'])
def update_contact_tags(contact_id):
    data = request.get_json()
    tags = data.get('tags')
    if not isinstance(tags, list):
        return jsonify({"error": "tags must be an array"}), 400
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact       = next((c for c in contacts_data.get("contacts", []) if c['id'] == contact_id), None)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
    contact['tags']       = tags
    contact['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_CONTACTS_FILE, contacts_data)
    return jsonify(contact)


@bp.route('/api/promo/contacts/by_tag/<tag>', methods=['GET'])
def list_contacts_by_tag(tag):
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    tag_lower     = tag.lower()
    filtered      = [c for c in contacts_data.get("contacts", [])
                     if any(t.lower() == tag_lower for t in c.get('tags', []))]
    return jsonify({"contacts": filtered})
