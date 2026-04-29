"""
CRM People — Contacts, Leads, Pipelines, Outreach KPI, Dashboard.

Data files:
  crm_contacts.json   — all contacts
  crm_leads.json      — leads with pipeline stage + communication log
  crm_pipelines.json  — pipeline definitions per product type
  crm_settings.json   — weekly outreach target, etc.
"""
import csv
import io
import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone, date

import requests as _requests
from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json

bp = Blueprint('crm_people', __name__)

# ── File paths ─────────────────────────────────────────────────────────────────

CRM_CONTACTS_FILE  = 'crm_contacts.json'
CRM_LEADS_FILE     = 'crm_leads.json'
CRM_PIPELINES_FILE = 'crm_pipelines.json'
CRM_SETTINGS_FILE  = 'crm_settings.json'

E164 = re.compile(r'^\+\d{7,15}$')

# ── Defaults ───────────────────────────────────────────────────────────────────

DEFAULT_PIPELINES = [
    {
        "id":           "retreat",
        "name":         "Retreat (Event)",
        "work_type":    "Retreat (Event)",
        "stages": [
            {"code": "enquiry",       "name": "Enquiry",       "order": 1},
            {"code": "qualified",     "name": "Qualified",     "order": 2},
            {"code": "proposal_sent", "name": "Proposal Sent", "order": 3},
            {"code": "negotiation",   "name": "Negotiation",   "order": 4},
        ],
        "won_label":        "Confirmed",
        "lost_label":       "Lost",
        "allow_cancelled":  False,
    },
    {
        "id":           "subscription",
        "name":         "Subscription",
        "work_type":    "Subscription",
        "stages": [
            {"code": "enquiry",     "name": "Enquiry",     "order": 1},
            {"code": "qualified",   "name": "Qualified",   "order": 2},
            {"code": "negotiation", "name": "Negotiation", "order": 3},
        ],
        "won_label":        "Won",
        "lost_label":       "Lost",
        "allow_cancelled":  True,
        "cancelled_label":  "Cancelled",
    },
]

DEFAULT_SETTINGS = {
    "weekly_outreach_target": 20,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_contacts():
    d = read_json(CRM_CONTACTS_FILE)
    if d is None:
        # Migrate from promo_contacts.json if it exists
        old = read_json('promo_contacts.json') or {}
        contacts = old.get('contacts', [])
        write_json(CRM_CONTACTS_FILE, {'contacts': contacts})
        return contacts
    return d.get('contacts', [])


def _save_contacts(contacts):
    write_json(CRM_CONTACTS_FILE, {'contacts': contacts})


def _get_leads():
    d = read_json(CRM_LEADS_FILE)
    if d is None:
        write_json(CRM_LEADS_FILE, {'leads': []})
        return []
    return d.get('leads', [])


def _save_leads(leads):
    write_json(CRM_LEADS_FILE, {'leads': leads})


def _get_pipelines():
    d = read_json(CRM_PIPELINES_FILE)
    if d is None:
        write_json(CRM_PIPELINES_FILE, DEFAULT_PIPELINES)
        return DEFAULT_PIPELINES
    return d


def _get_settings():
    d = read_json(CRM_SETTINGS_FILE)
    if d is None:
        write_json(CRM_SETTINGS_FILE, DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    return d


def _now():
    return datetime.utcnow().isoformat() + 'Z'


def _week_bounds(week_start_str=None):
    """Return (monday, sunday) as date objects for the requested week."""
    if week_start_str:
        try:
            monday = date.fromisoformat(week_start_str)
        except ValueError:
            monday = date.today()
    else:
        today  = date.today()
        monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


# ── Contacts ───────────────────────────────────────────────────────────────────

@bp.route('/api/crm/contacts', methods=['GET'])
def list_contacts():
    q = (request.args.get('q') or '').lower()
    contacts = _get_contacts()
    if q:
        contacts = [c for c in contacts
                    if q in c.get('name','').lower()
                    or q in c.get('phone','').lower()
                    or q in c.get('email','').lower()]
    return jsonify({'contacts': contacts})


@bp.route('/api/crm/contacts', methods=['POST'])
def create_contact():
    data  = request.get_json() or {}
    name  = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    if phone and not E164.match(phone):
        return jsonify({'error': 'Phone must be E.164 format, e.g. +27821234567'}), 400

    contacts = _get_contacts()
    if phone and any(c.get('phone') == phone for c in contacts):
        return jsonify({'error': 'A contact with this phone number already exists'}), 409

    now = _now()
    contact = {
        'id':         str(uuid.uuid4()),
        'name':       name,
        'phone':      phone,
        'email':      data.get('email', '').strip(),
        'notes':      data.get('notes', '').strip(),
        'source':     data.get('source', 'manual'),
        'created_at': now,
        'updated_at': now,
    }
    contacts.append(contact)
    _save_contacts(contacts)
    return jsonify(contact), 201


@bp.route('/api/crm/contacts/<contact_id>', methods=['PUT'])
def update_contact(contact_id):
    data     = request.get_json() or {}
    contacts = _get_contacts()
    contact  = next((c for c in contacts if c['id'] == contact_id), None)
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    for field in ('name', 'phone', 'email', 'notes', 'source'):
        if field in data:
            contact[field] = data[field].strip() if isinstance(data[field], str) else data[field]
    contact['updated_at'] = _now()
    _save_contacts(contacts)
    return jsonify(contact)


@bp.route('/api/crm/contacts/<contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    contacts = _get_contacts()
    original = len(contacts)
    contacts = [c for c in contacts if c['id'] != contact_id]
    if len(contacts) == original:
        return jsonify({'error': 'Contact not found'}), 404
    _save_contacts(contacts)
    return jsonify({'ok': True})


@bp.route('/api/crm/contacts/import', methods=['POST'])
def import_contacts():
    """
    CSV import. Expected columns (flexible header matching):
      name / Name, phone / Phone / Number, email / Email,
      lead / Lead / lead type / Lead Type  (optional — work title to create a lead)
    Skips duplicates by phone number.
    When a Lead column is present, looks up the work by title in catalog_works.json,
    resolves the pipeline from the work type, and creates a CRM lead for each new contact.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']

    stream   = io.StringIO(file.stream.read().decode('utf-8-sig'), newline=None)
    reader   = csv.DictReader(stream)
    contacts = _get_contacts()
    existing_phones = {c.get('phone') for c in contacts}

    imported      = 0
    skipped       = 0
    leads_created = 0
    errors        = []
    now           = _now()

    # Flexible header matching
    def _col(row, *keys):
        for k in keys:
            for rk in row:
                if rk.strip().lower() == k.lower():
                    return row[rk].strip()
        return ''

    # Build work-title → work lookup and pipeline work_type → pipeline_id map once
    from utils.json_store import read_json as _rj
    catalog     = _rj('catalog_works.json') or {'works': []}
    works_by_title = {w.get('title', '').lower(): w for w in catalog.get('works', [])}

    pipelines = _get_pipelines()
    # work_type → pipeline_id (e.g. "Subscription" → "subscription")
    pipeline_by_wtype = {p.get('work_type', ''): p for p in pipelines if p.get('work_type')}

    new_leads = []

    for i, row in enumerate(reader, start=2):
        name       = _col(row, 'name', 'Name', 'full name', 'Full Name')
        phone      = _col(row, 'phone', 'Phone', 'number', 'Number',
                          'phone number', 'Phone Number', 'mobile', 'Mobile')
        email      = _col(row, 'email', 'Email')
        lead_title = _col(row, 'lead', 'Lead', 'lead type', 'Lead Type')

        if not name:
            errors.append(f'Row {i}: missing name')
            skipped += 1
            continue

        # Normalise phone: strip spaces/dashes, ensure + prefix
        phone = re.sub(r'[\s\-()]', '', phone)
        if phone and not phone.startswith('+'):
            phone = '+' + phone
        if phone and not E164.match(phone):
            errors.append(f'Row {i} ({name}): invalid phone "{phone}" — skipped')
            skipped += 1
            continue
        if phone and phone in existing_phones:
            skipped += 1
            continue

        contact = {
            'id':         str(uuid.uuid4()),
            'name':       name,
            'phone':      phone,
            'email':      email,
            'notes':      '',
            'source':     'csv',
            'created_at': now,
            'updated_at': now,
        }
        contacts.append(contact)
        if phone:
            existing_phones.add(phone)
        imported += 1

        # Create a lead if a Lead column value was provided
        if lead_title:
            work = works_by_title.get(lead_title.lower())
            if not work:
                errors.append(f'Row {i} ({name}): lead type "{lead_title}" not found — lead skipped')
            else:
                pipeline = pipeline_by_wtype.get(work.get('work_type', ''))
                if not pipeline:
                    errors.append(
                        f'Row {i} ({name}): no pipeline for work type '
                        f'"{work.get("work_type","")}" — lead skipped'
                    )
                else:
                    first_stage = pipeline['stages'][0]['code'] if pipeline.get('stages') else 'enquiry'
                    lead = {
                        'id':                str(uuid.uuid4()),
                        'contact_id':        contact['id'],
                        'contact_name':      name,
                        'contact_phone':     phone,
                        'pipeline_id':       pipeline['id'],
                        'pipeline_name':     pipeline['name'],
                        'work_id':           work.get('id', ''),
                        'work_title':        work.get('title', ''),
                        'stage':             first_stage,
                        'status':            'open',
                        'value':             float(work.get('price') or 0),
                        'notes':             '',
                        'communication_log': [],
                        'created_at':        now,
                        'updated_at':        now,
                    }
                    new_leads.append(lead)
                    leads_created += 1

    _save_contacts(contacts)

    if new_leads:
        leads = _get_leads()
        leads.extend(new_leads)
        _save_leads(leads)

    return jsonify({
        'imported':      imported,
        'skipped':       skipped,
        'leads_created': leads_created,
        'errors':        errors,
    })


@bp.route('/api/crm/contacts/bulk_message', methods=['POST'])
def bulk_message_contacts():
    """
    Send a WhatsApp message to multiple contacts with 3-minute stagger.
    Body: { contact_ids: [...], content: "...", scheduled_at: "ISO"|null }
    If scheduled_at is null → first message sends immediately, rest are
    scheduled at +3, +6, +9 … minutes from now.
    If scheduled_at is set  → messages start at that time, then +3, +6 … min.
    """
    data         = request.get_json() or {}
    contact_ids  = data.get('contact_ids', [])
    content      = data.get('content', '').strip()
    scheduled_at = data.get('scheduled_at')  # ISO string or None

    if not contact_ids:
        return jsonify({'error': 'No contacts selected'}), 400
    if not content:
        return jsonify({'error': 'Message content is required'}), 400

    contacts = _get_contacts()
    leads    = _get_leads()
    now      = datetime.utcnow().replace(tzinfo=timezone.utc)
    delay_minutes = 3

    # Parse base time for scheduled send
    base_dt = None
    if scheduled_at:
        try:
            base_dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Invalid scheduled_at format'}), 400

    results = []
    leads_updated = False

    for i, contact_id in enumerate(contact_ids):
        contact = next((c for c in contacts if c['id'] == contact_id), None)
        if not contact:
            results.append({'contact_id': contact_id, 'error': 'Contact not found'})
            continue

        phone = contact.get('phone', '').strip()
        if not phone:
            results.append({'contact_id': contact_id,
                            'contact_name': contact.get('name', ''),
                            'error': 'No phone number'})
            continue

        # Staggered delivery time
        if i == 0 and not scheduled_at:
            msg_scheduled_at = None          # first message: send immediately
        elif scheduled_at:
            msg_dt = base_dt + timedelta(minutes=i * delay_minutes)
            msg_scheduled_at = msg_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            msg_dt = now + timedelta(minutes=i * delay_minutes)
            msg_scheduled_at = msg_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Find the most recent open lead for this contact (for logging)
        contact_leads = [l for l in leads
                         if l.get('contact_id') == contact_id and l.get('status') == 'open']
        latest_lead   = max(contact_leads, key=lambda l: l.get('updated_at', ''), default=None)

        try:
            from services.distribution_service import push_to_outbox
            result = push_to_outbox(
                recipient_phone=phone,
                recipient_name=contact.get('name', ''),
                content=content,
                source='crm_outreach',
                scheduled_at=msg_scheduled_at,
                contact_id=contact_id,
                lead_id=latest_lead['id'] if latest_lead else None,
                pipeline_id=latest_lead.get('pipeline_id', '') if latest_lead else None,
            )
        except Exception as e:
            results.append({'contact_id': contact_id,
                            'contact_name': contact.get('name', ''),
                            'error': str(e)})
            continue

        # Log to lead's communication_log if a lead exists
        if latest_lead:
            ts = msg_scheduled_at or (now.strftime('%Y-%m-%dT%H:%M:%SZ'))
            entry = {
                'id':           str(uuid.uuid4()),
                'direction':    'outbound',
                'channel':      'whatsapp',
                'content':      content,
                'contact_name': contact.get('name', ''),
                'logged_via':   'crm',
                'sent_at':      ts,
                'status':       'scheduled' if msg_scheduled_at else 'sent',
                'message_id':   result.get('id'),
            }
            latest_lead.setdefault('communication_log', []).append(entry)
            latest_lead['updated_at'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
            leads_updated = True

        results.append({
            'contact_id':   contact_id,
            'contact_name': contact.get('name', ''),
            'phone':        phone,
            'message_id':   result.get('id'),
            'ec2_synced':   result.get('ec2_synced'),
            'scheduled_at': msg_scheduled_at,
        })

    if leads_updated:
        _save_leads(leads)

    sent    = sum(1 for r in results if 'message_id' in r)
    failed  = sum(1 for r in results if 'error' in r)
    return jsonify({'results': results, 'sent': sent, 'failed': failed})


# ── Leads ──────────────────────────────────────────────────────────────────────

@bp.route('/api/crm/leads', methods=['GET'])
def list_leads():
    pipeline_id = request.args.get('pipeline_id')
    contact_id  = request.args.get('contact_id')
    status      = request.args.get('status')  # open|won|lost|cancelled

    leads = _get_leads()
    if pipeline_id:
        leads = [l for l in leads if l.get('pipeline_id') == pipeline_id]
    if contact_id:
        leads = [l for l in leads if l.get('contact_id') == contact_id]
    if status:
        leads = [l for l in leads if l.get('status') == status]

    return jsonify({'leads': leads})


@bp.route('/api/crm/leads', methods=['POST'])
def create_lead():
    data       = request.get_json() or {}
    contact_id = data.get('contact_id', '').strip()
    pipeline_id = data.get('pipeline_id', '').strip()
    work_id    = data.get('work_id', '').strip()
    work_title = data.get('work_title', '').strip()
    value      = float(data.get('value') or 0)
    notes      = data.get('notes', '').strip()

    if not contact_id or not pipeline_id:
        return jsonify({'error': 'contact_id and pipeline_id are required'}), 400

    contacts = _get_contacts()
    contact  = next((c for c in contacts if c['id'] == contact_id), None)
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404

    pipelines = _get_pipelines()
    pipeline  = next((p for p in pipelines if p['id'] == pipeline_id), None)
    if not pipeline:
        return jsonify({'error': 'Pipeline not found'}), 404

    first_stage = pipeline['stages'][0]['code'] if pipeline['stages'] else 'enquiry'
    now = _now()

    lead = {
        'id':                str(uuid.uuid4()),
        'contact_id':        contact_id,
        'contact_name':      contact['name'],
        'contact_phone':     contact.get('phone', ''),
        'pipeline_id':       pipeline_id,
        'pipeline_name':     pipeline['name'],
        'work_id':           work_id,
        'work_title':        work_title,
        'stage':             first_stage,
        'status':            'open',
        'value':             value,
        'notes':             notes,
        'communication_log': [],
        'created_at':        now,
        'updated_at':        now,
    }
    leads = _get_leads()
    leads.append(lead)
    _save_leads(leads)
    return jsonify(lead), 201


@bp.route('/api/crm/leads/<lead_id>', methods=['GET'])
def get_lead(lead_id):
    lead = next((l for l in _get_leads() if l['id'] == lead_id), None)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    return jsonify(lead)


@bp.route('/api/crm/leads/<lead_id>', methods=['PUT'])
def update_lead(lead_id):
    data  = request.get_json() or {}
    leads = _get_leads()
    lead  = next((l for l in leads if l['id'] == lead_id), None)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    for field in ('stage', 'value', 'notes', 'work_id', 'work_title'):
        if field in data:
            lead[field] = data[field]
    lead['updated_at'] = _now()
    _save_leads(leads)
    return jsonify(lead)


@bp.route('/api/crm/leads/<lead_id>', methods=['DELETE'])
def delete_lead(lead_id):
    leads    = _get_leads()
    original = len(leads)
    leads    = [l for l in leads if l['id'] != lead_id]
    if len(leads) == original:
        return jsonify({'error': 'Lead not found'}), 404
    _save_leads(leads)
    return jsonify({'ok': True})


@bp.route('/api/crm/leads/<lead_id>/stage', methods=['PUT'])
def move_stage(lead_id):
    """Move lead to a different pipeline stage (must still be open)."""
    data  = request.get_json() or {}
    stage = data.get('stage', '').strip()
    if not stage:
        return jsonify({'error': 'stage is required'}), 400

    leads = _get_leads()
    lead  = next((l for l in leads if l['id'] == lead_id), None)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    if lead.get('status') != 'open':
        return jsonify({'error': 'Cannot move a closed lead'}), 409

    # Validate stage exists in pipeline
    pipelines = _get_pipelines()
    pipeline  = next((p for p in pipelines if p['id'] == lead.get('pipeline_id')), None)
    if pipeline:
        valid = [s['code'] for s in pipeline.get('stages', [])]
        if stage not in valid:
            return jsonify({'error': f'Invalid stage "{stage}" for pipeline "{pipeline["id"]}"'}), 400

    lead['stage']      = stage
    lead['updated_at'] = _now()
    _save_leads(leads)
    return jsonify(lead)


@bp.route('/api/crm/leads/<lead_id>/close', methods=['POST'])
def close_lead(lead_id):
    """
    Close a lead as won / lost / cancelled.
    Body: { "outcome": "won" | "lost" | "cancelled", "notes": "..." }
    Cancelled is only valid for subscription pipeline (post-win).
    """
    data    = request.get_json() or {}
    outcome = data.get('outcome', '').strip()
    if outcome not in ('won', 'lost', 'cancelled'):
        return jsonify({'error': 'outcome must be won, lost, or cancelled'}), 400

    leads = _get_leads()
    lead  = next((l for l in leads if l['id'] == lead_id), None)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    if outcome == 'cancelled':
        pipelines = _get_pipelines()
        pipeline  = next((p for p in pipelines if p['id'] == lead.get('pipeline_id')), None)
        if pipeline and not pipeline.get('allow_cancelled'):
            return jsonify({'error': 'Cancelled outcome not allowed for this pipeline'}), 400

    now = _now()
    lead['status']     = outcome
    lead['updated_at'] = now
    lead[f'{outcome}_at'] = now
    if data.get('notes'):
        lead['notes'] = data['notes']
    _save_leads(leads)
    return jsonify(lead)


@bp.route('/api/crm/leads/<lead_id>/reopen', methods=['POST'])
def reopen_lead(lead_id):
    """Reopen a closed lead back to open status."""
    leads = _get_leads()
    lead  = next((l for l in leads if l['id'] == lead_id), None)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    lead['status']     = 'open'
    lead['updated_at'] = _now()
    _save_leads(leads)
    return jsonify(lead)


# ── Communication log ──────────────────────────────────────────────────────────

@bp.route('/api/crm/leads/<lead_id>/messages', methods=['POST'])
def log_message(lead_id):
    """
    Log an outreach message against a lead.
    Body:
      { "content": "...", "logged_via": "crm" | "manual",
        "contact_name": "...", "sent_at": "ISO or null",
        "scheduled_at": "ISO or null" }
    If logged_via == "crm", queues to EC2 (immediately or at scheduled_at).
    Stats only count this message once EC2 confirms it was sent (status: sent).
    """
    data         = request.get_json() or {}
    content      = data.get('content', '').strip()
    logged_via   = data.get('logged_via', 'manual')
    contact_name = data.get('contact_name', '').strip()
    sent_at      = data.get('sent_at') or _now()
    scheduled_at = data.get('scheduled_at')  # future ISO string → scheduled send

    if not content:
        return jsonify({'error': 'content is required'}), 400

    leads = _get_leads()
    lead  = next((l for l in leads if l['id'] == lead_id), None)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    is_scheduled = bool(scheduled_at and logged_via == 'crm')

    entry = {
        'id':           str(uuid.uuid4()),
        'direction':    'outbound',
        'channel':      'whatsapp',
        'content':      content,
        'contact_name': contact_name or lead.get('contact_name', ''),
        'logged_via':   logged_via,
        'sent_at':      scheduled_at if is_scheduled else sent_at,
        'status':       'scheduled' if is_scheduled else 'sent',
    }
    # Manual log entries have no status (backwards compatible — counted in stats)
    if logged_via == 'manual':
        entry.pop('status', None)

    gowa_result = None
    if logged_via == 'crm':
        phone = lead.get('contact_phone', '').strip()
        if phone:
            try:
                from services.distribution_service import push_to_outbox
                result = push_to_outbox(
                    recipient_phone=phone,
                    recipient_name=lead.get('contact_name', ''),
                    content=content,
                    source='crm_outreach',
                    scheduled_at=scheduled_at if is_scheduled else sent_at,
                    lead_id=lead_id,
                    pipeline_id=lead.get('pipeline_id', ''),
                )
                entry['message_id'] = result.get('id')
                gowa_result = result
            except Exception as e:
                entry['send_error'] = str(e)

    lead.setdefault('communication_log', []).append(entry)
    lead['updated_at'] = _now()
    _save_leads(leads)

    return jsonify({'entry': entry, 'gowa': gowa_result})


@bp.route('/api/crm/leads/<lead_id>/messages/<msg_id>', methods=['DELETE'])
def delete_log_entry(lead_id, msg_id):
    leads = _get_leads()
    lead  = next((l for l in leads if l['id'] == lead_id), None)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    before = len(lead.get('communication_log', []))
    lead['communication_log'] = [e for e in lead.get('communication_log', [])
                                  if e['id'] != msg_id]
    if len(lead['communication_log']) == before:
        return jsonify({'error': 'Message not found'}), 404
    lead['updated_at'] = _now()
    _save_leads(leads)
    return jsonify({'ok': True})


# ── AI Message Generation ──────────────────────────────────────────────────────

_SALES_SYSTEM_PROMPT = """You are a WhatsApp sales message writer for an independent creator selling a low-cost subscription product.

STRICT RULES:
- Word count: 12–35 words (hard cap)
- Maximum 3 sentences, prefer 2
- Exactly ONE clear ask per message
- Simple, spoken language — sound like a real person texting
- Use first name once only. No "Dear", no formal greetings
- Use contractions (I'm, you're, etc.)
- Calm, confident, neutral tone. Not excited, not desperate
- No exclamation marks
- No emojis (default)
- No begging, no emotional pressure, no long explanations
- No "it's just R30" framing
- No gratitude-heavy phrasing, no storytelling
- No jargon, no corporate language

MESSAGE STRUCTURE:
1. Light context (why message exists)
2. Framing (group / participation / inclusion)
3. Clear ask (1 sentence)

PERSUASION (use sparingly):
- Social proof: "a few people already joined"
- Scarcity: "closing this soon", "few spots"
- Inclusion: "small group", "early supporters"

STAGE-SPECIFIC FRAMING:
- enquiry: soft invite — they showed interest, invite them in
- qualified: direct inclusion — you know they're real, ask them directly
- negotiation: reframe value, not price — "less about R30, more about being part of early group"
- re-engagement: reference past connection — "you were part of this before"
- follow_up: low-pressure nudge — "just circling back once"

OUTPUT: Respond ONLY with valid JSON in this exact format:
{"message": "<12–35 word WhatsApp message>", "stage": "<stage>", "tone_note": "<max 15 words explaining tone>"}
No extra text before or after the JSON."""


@bp.route('/api/crm/leads/<lead_id>/generate_message', methods=['POST'])
def generate_message(lead_id):
    leads = _get_leads()
    lead  = next((l for l in leads if l['id'] == lead_id), None)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    # Build context for the AI
    log      = lead.get('communication_log') or []
    log_sorted = sorted(log, key=lambda e: e.get('sent_at') or '')
    last_inbound = next(
        (e['content'] for e in reversed(log_sorted) if e.get('direction') == 'inbound'), None
    )
    last_contact_days = None
    if log_sorted:
        try:
            last_ts = datetime.fromisoformat(
                (log_sorted[-1].get('sent_at') or '').replace('Z', '+00:00')
            )
            last_contact_days = (datetime.now(timezone.utc) - last_ts).days
        except Exception:
            pass

    stage = lead.get('stage') or 'enquiry'
    context = {
        'lead_name':              lead.get('contact_name', '').split()[0],
        'pipeline':               lead.get('pipeline_name') or lead.get('pipeline_id'),
        'stage':                  stage,
        'product':                lead.get('work_title') or '',
        'notes':                  lead.get('notes') or '',
        'last_inbound_message':   last_inbound or '',
        'days_since_last_contact': last_contact_days,
    }

    user_prompt = (
        f"Generate a WhatsApp sales message for this lead:\n{json.dumps(context, indent=2)}"
    )

    try:
        from services.ai_service import call_ai
        from utils.json_store import read_json

        # Load system prompt from asset_prompts (editable via Settings → Prompts tab)
        promo = read_json('promo_settings.json') or {}
        asset_prompts = promo.get('asset_prompts') or []
        cfg = next((p for p in asset_prompts if p.get('asset_type') == 'sales_message'), None)
        active_ver = (cfg or {}).get('active_version', 'A')
        system_prompt = ((cfg or {}).get('versions', {}).get(active_ver, {}).get('prompt') or '').strip()
        if not system_prompt:
            system_prompt = _SALES_SYSTEM_PROMPT  # fallback to hardcoded default

        raw = call_ai(
            'sales_message',
            [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_prompt},
            ],
            max_tokens=200,
            temperature=0.7,
        )
        # Parse JSON — strip markdown fences if any
        import re as _re
        clean = _re.sub(r'^```[a-z]*\s*|\s*```$', '', raw.strip(), flags=_re.MULTILINE).strip()
        result = json.loads(clean)
        return jsonify(result)
    except json.JSONDecodeError:
        # Return raw text as message if JSON parse fails
        return jsonify({'message': raw.strip(), 'stage': stage, 'tone_note': ''})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Pipelines ──────────────────────────────────────────────────────────────────

@bp.route('/api/crm/pipelines', methods=['GET'])
def list_pipelines():
    return jsonify(_get_pipelines())


# ── Settings ───────────────────────────────────────────────────────────────────

@bp.route('/api/crm/settings', methods=['GET'])
def get_settings():
    return jsonify(_get_settings())


@bp.route('/api/crm/settings', methods=['PUT'])
def update_settings():
    data     = request.get_json() or {}
    settings = _get_settings()
    if 'weekly_outreach_target' in data:
        try:
            settings['weekly_outreach_target'] = int(data['weekly_outreach_target'])
        except (ValueError, TypeError):
            return jsonify({'error': 'weekly_outreach_target must be an integer'}), 400
    write_json(CRM_SETTINGS_FILE, settings)
    return jsonify(settings)


# ── Outreach KPI ───────────────────────────────────────────────────────────────

@bp.route('/api/crm/outreach/weekly', methods=['GET'])
def weekly_outreach():
    """
    Returns daily outreach counts for the requested week, split by pipeline.
    Query param: week_start=YYYY-MM-DD (defaults to current Monday)
    """
    monday, sunday = _week_bounds(request.args.get('week_start'))
    settings = _get_settings()
    target   = settings.get('weekly_outreach_target', 20)

    leads    = _get_leads()
    pipelines = _get_pipelines()
    pipeline_names = {p['id']: p['name'] for p in pipelines}

    # Collect all log entries for the week
    DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    # Structure: {pipeline_id: {day_index: count}}
    counts = defaultdict(lambda: [0] * 7)

    for lead in leads:
        pid = lead.get('pipeline_id', 'other')
        for entry in lead.get('communication_log', []):
            # Exclude messages that are still pending scheduled delivery
            if entry.get('status') == 'scheduled':
                continue
            sent_raw = entry.get('sent_at', '')
            try:
                sent_dt = datetime.fromisoformat(sent_raw.replace('Z', '+00:00'))
                sent_date = sent_dt.date()
            except (ValueError, AttributeError):
                continue
            if monday <= sent_date <= sunday:
                day_idx = (sent_date - monday).days
                counts[pid][day_idx] += 1

    # Build per-pipeline rows
    rows = []
    total_by_day = [0] * 7
    grand_total  = 0
    for pid, daily in counts.items():
        row_total = sum(daily)
        grand_total += row_total
        for i, v in enumerate(daily):
            total_by_day[i] += v
        rows.append({
            'pipeline_id':   pid,
            'pipeline_name': pipeline_names.get(pid, pid),
            'daily':         daily,
            'total':         row_total,
        })

    return jsonify({
        'week_start':    monday.isoformat(),
        'week_end':      sunday.isoformat(),
        'days':          DAYS,
        'target':        target,
        'grand_total':   grand_total,
        'hit_target':    grand_total >= target,
        'rows':          rows,
        'total_by_day':  total_by_day,
    })


@bp.route('/api/crm/outreach/report', methods=['GET'])
def outreach_report_text():
    """Returns a plain-text weekly report suitable for copy-pasting."""
    monday, sunday = _week_bounds(request.args.get('week_start'))
    data = weekly_outreach().get_json()

    lines = [
        f"OUTREACH REPORT — Week of {monday.strftime('%d %b %Y')}",
        '─' * 44,
    ]
    for row in data.get('rows', []):
        daily_str = ' · '.join(
            f"{d} {v}" for d, v in zip(data['days'], row['daily'])
        )
        lines.append(f"{row['pipeline_name']:20} {daily_str}  = {row['total']}")

    lines.append('─' * 44)
    total   = data['grand_total']
    target  = data['target']
    status  = '✅ HIT' if data['hit_target'] else '❌ MISSED'
    lines.append(f"TOTAL: {total} / {target} target  {status}")

    return jsonify({'report': '\n'.join(lines)})


# ── Scheduled message sync ────────────────────────────────────────────────────

@bp.route('/api/crm/outreach/sync_scheduled', methods=['POST'])
def sync_scheduled_messages():
    """
    Reconcile scheduled CRM messages back from EC2 once they've been sent.

    Looks through every lead's communication_log for entries with status='scheduled'
    and a message_id. Checks each against the EC2 queue:
    - If EC2 reports 'sent': updates entry to status='sent', sets actual sent_at
    - If EC2 reports 'failed': updates entry to status='failed'
    - If EC2 has no record (message was processed and removed): treats as sent

    Only after this update will the message count in outreach stats.
    """
    ec2_url = os.environ.get('EC2_SENDER_URL', 'http://13.218.60.13:5555').rstrip('/')

    # Fetch full EC2 queue to check message statuses
    try:
        r = _requests.get(f'{ec2_url}/queue', auth=('admin', 'admin'), timeout=10)
        r.raise_for_status()
        ec2_queue = r.json()
    except Exception as e:
        return jsonify({'error': f'Could not reach EC2: {e}', 'updated': 0}), 502

    ec2_map = {m['id']: m for m in ec2_queue if 'id' in m}

    leads   = _get_leads()
    now     = _now()
    updated = 0
    details = []

    for lead in leads:
        changed = False
        for entry in lead.get('communication_log', []):
            if entry.get('status') != 'scheduled':
                continue
            msg_id = entry.get('message_id')
            if not msg_id:
                continue

            ec2_msg = ec2_map.get(msg_id)
            if ec2_msg is None:
                # Not in queue — EC2 has processed and removed it; treat as sent
                entry['status']  = 'sent'
                entry['sent_at'] = now
                changed = True
                updated += 1
                details.append({'lead_id': lead['id'], 'msg_id': msg_id, 'result': 'sent_removed'})
            elif ec2_msg.get('status') == 'sent':
                entry['status']  = 'sent'
                entry['sent_at'] = ec2_msg.get('sent_at') or now
                changed = True
                updated += 1
                details.append({'lead_id': lead['id'], 'msg_id': msg_id, 'result': 'sent'})
            elif ec2_msg.get('status') == 'failed':
                entry['status'] = 'failed'
                changed = True
                updated += 1
                details.append({'lead_id': lead['id'], 'msg_id': msg_id, 'result': 'failed'})

        if changed:
            lead['updated_at'] = now

    if updated:
        _save_leads(leads)

    return jsonify({'updated': updated, 'details': details})


# ── Inbound WhatsApp sync ─────────────────────────────────────────────────────

@bp.route('/api/crm/leads/sync_inbound', methods=['POST'])
def sync_inbound():
    """
    Poll EC2 sender for unconsumed inbound WhatsApp messages, match each by
    sender phone to a lead's contact_phone, and append an inbound entry to
    that lead's communication_log.  Acknowledges consumed IDs back to EC2.

    Returns: { "synced": N, "unmatched": N, "entries": [...] }
    """
    ec2_url = os.environ.get('EC2_SENDER_URL', 'http://13.218.60.13:5555').rstrip('/')

    # Fetch unconsumed inbound messages from EC2
    try:
        r = _requests.get(f'{ec2_url}/inbound', auth=('admin', 'admin'), timeout=10)
        r.raise_for_status()
        inbound = r.json()
    except Exception as e:
        return jsonify({'error': f'Could not reach EC2: {e}'}), 502

    if not inbound:
        return jsonify({'synced': 0, 'unmatched': 0, 'entries': []})

    leads    = _get_leads()

    # Build phone → lead index (normalise to digits only for matching)
    def _digits(p):
        return re.sub(r'\D', '', p or '')

    phone_to_lead = {}
    for lead in leads:
        raw = lead.get('contact_phone', '')
        d   = _digits(raw)
        # Strip leading country-code variants so +27821234567 matches 27821234567
        for candidate in {d, d.lstrip('0'), d[2:] if d.startswith('27') else d}:
            if candidate:
                phone_to_lead[candidate] = lead

    now     = _now()
    synced  = 0
    unmatched = 0
    entries = []
    consumed_ids = []

    for msg in inbound:
        sender_digits = _digits(msg.get('phone', ''))
        lead = None
        # Try the full number, then without leading 27, then without leading 0
        for variant in [sender_digits,
                        sender_digits[2:] if sender_digits.startswith('27') else sender_digits,
                        sender_digits.lstrip('0')]:
            lead = phone_to_lead.get(variant)
            if lead:
                break

        consumed_ids.append(msg['id'])   # always consume — even unmatched

        if lead is None:
            unmatched += 1
            continue

        # Dedup: skip if wa_msg_id already in communication_log
        existing_ids = {e.get('wa_msg_id') for e in lead.get('communication_log', [])}
        if msg['id'] in existing_ids:
            continue  # already logged; still consumed above

        entry = {
            'id':           str(uuid.uuid4()),
            'direction':    'inbound',
            'channel':      'whatsapp',
            'content':      msg['text'],
            'contact_name': msg.get('from_name') or lead.get('contact_name', ''),
            'logged_via':   'auto_sync',
            'sent_at':      msg.get('timestamp', now),
            'wa_msg_id':    msg['id'],
        }
        lead.setdefault('communication_log', []).append(entry)
        lead['updated_at'] = now
        synced += 1
        entries.append({'lead_id': lead['id'], 'entry': entry})

    if synced:
        _save_leads(leads)

    # Acknowledge consumed IDs back to EC2
    if consumed_ids:
        try:
            _requests.post(
                f'{ec2_url}/inbound/consume',
                json=consumed_ids,
                auth=('admin', 'admin'),
                timeout=10,
            )
        except Exception:
            pass   # non-fatal — messages will be re-fetched next sync but deduped by wa_msg_id

    return jsonify({'synced': synced, 'unmatched': unmatched, 'entries': entries})


# ── Dashboard ──────────────────────────────────────────────────────────────────

@bp.route('/api/crm/dashboard', methods=['GET'])
def dashboard():
    leads     = _get_leads()
    pipelines = _get_pipelines()
    pipeline_names = {p['id']: p['name'] for p in pipelines}

    # Revenue totals
    won_total       = sum(l.get('value', 0) for l in leads if l.get('status') == 'won')
    lost_total      = sum(l.get('value', 0) for l in leads if l.get('status') == 'lost')
    cancelled_total = sum(l.get('value', 0) for l in leads if l.get('status') == 'cancelled')
    pipeline_total  = sum(l.get('value', 0) for l in leads if l.get('status') == 'open')

    # This month
    now_month = datetime.utcnow().strftime('%Y-%m')
    won_month = sum(
        l.get('value', 0) for l in leads
        if l.get('status') == 'won' and (l.get('won_at') or '')[:7] == now_month
    )

    # Per-pipeline stage breakdown (open leads only)
    pipeline_breakdown = {}
    for p in pipelines:
        pid    = p['id']
        stages = p.get('stages', [])
        breakdown = []
        for s in stages:
            code  = s['code']
            items = [l for l in leads
                     if l.get('pipeline_id') == pid
                     and l.get('status') == 'open'
                     and l.get('stage') == code]
            breakdown.append({
                'stage':   s['name'],
                'code':    code,
                'count':   len(items),
                'value':   sum(i.get('value', 0) for i in items),
            })
        pipeline_breakdown[pid] = {
            'name':      p['name'],
            'breakdown': breakdown,
            'open':      sum(1 for l in leads if l.get('pipeline_id') == pid and l.get('status') == 'open'),
            'won':       sum(1 for l in leads if l.get('pipeline_id') == pid and l.get('status') == 'won'),
            'lost':      sum(1 for l in leads if l.get('pipeline_id') == pid and l.get('status') == 'lost'),
        }

    return jsonify({
        'revenue': {
            'won_all_time':       won_total,
            'won_this_month':     won_month,
            'lost_all_time':      lost_total,
            'cancelled_all_time': cancelled_total,
            'pipeline_value':     pipeline_total,
        },
        'pipelines': pipeline_breakdown,
        'total_contacts': len(_get_contacts()),
        'total_leads':    len(leads),
        'open_leads':     sum(1 for l in leads if l.get('status') == 'open'),
    })
