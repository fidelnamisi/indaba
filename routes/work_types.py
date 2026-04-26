"""
Work Types Registry — defines the categories of creative work the system supports.
"""
from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json

bp = Blueprint('work_types', __name__)

WORK_TYPES_FILE = 'work_types.json'

DEFAULT_WORK_TYPES = [
    {
        "key":                  "Book",
        "name":                 "Book",
        "description":          "A full-length novel or non-fiction book organized into chapters.",
        "essential_asset_key":  "prose",
        "essential_asset_label":"Chapter Prose"
    },
    {
        "key":                  "Podcast",
        "name":                 "Podcast",
        "description":          "An audio podcast series organized into episodes.",
        "essential_asset_key":  "audio_notes",
        "essential_asset_label":"Audio Notes / Script"
    },
    {
        "key":                  "Fundraising Campaign",
        "name":                 "Fundraising Campaign",
        "description":          "A time-bound fundraising initiative organized into campaign modules.",
        "essential_asset_key":  "campaign_narrative",
        "essential_asset_label":"Campaign Narrative"
    },
    {
        "key":                  "Retreat (Event)",
        "name":                 "Retreat (Event)",
        "description":          "A retreat or live event organized into offer modules.",
        "essential_asset_key":  "event_offer",
        "essential_asset_label":"Event Offer Write-up"
    },
    {
        "key":                  "Subscription",
        "name":                 "Subscription",
        "description":          "A recurring subscription product organized into edition modules.",
        "essential_asset_key":  "edition_content",
        "essential_asset_label":"Edition Content"
    },
]


def get_work_types():
    """Return work types, seeding defaults on first run."""
    data = read_json(WORK_TYPES_FILE)
    if data is None:
        write_json(WORK_TYPES_FILE, DEFAULT_WORK_TYPES)
        return DEFAULT_WORK_TYPES
    return data


@bp.route('/api/work-types', methods=['GET'])
def list_work_types():
    return jsonify(get_work_types())


@bp.route('/api/work-types', methods=['PUT'])
def update_work_types():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({"error": "Work types must be a JSON array"}), 400
    for wt in data:
        if not wt.get('key') or not wt.get('name'):
            return jsonify({"error": "Each work type must have key and name"}), 400
    write_json(WORK_TYPES_FILE, data)
    return jsonify(data)
