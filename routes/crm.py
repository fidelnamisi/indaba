"""
CRM routes — pipeline summary, AI suggestions.
Detailed contact/lead CRUD is in promo_contacts.py and promo_leads.py.
"""
from flask import Blueprint, jsonify, request
from utils.json_store import read_json
from utils.constants import PROMO_LEADS_FILE, PROMO_CONTACTS_FILE

bp = Blueprint('crm', __name__)


@bp.route('/api/promo/pipeline', methods=['GET'])
def get_crm_pipeline():
    """Returns all leads grouped by stage."""
    from utils.constants import LEAD_STAGES
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads      = leads_data.get("leads", [])
    pipeline   = {stage: [] for stage in LEAD_STAGES}
    for lead in leads:
        stage = lead.get('stage', 'lead')
        if stage in pipeline:
            pipeline[stage].append(lead)
    return jsonify({"pipeline": pipeline, "total": len(leads)})
