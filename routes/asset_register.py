"""
Asset Register — global registry of asset types and their work-type assignments.
"""
from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json

bp = Blueprint('asset_register', __name__)

ASSET_REGISTER_FILE = 'asset_register.json'

DEFAULT_ASSET_REGISTER = [
    {
        "key":         "synopsis",
        "name":        "Synopsis",
        "role":        "supporting",
        "description": "Structured summary of the module. Primary input for blurb, tagline, and image prompt generation.",
        "ai_generated": True,
        "work_types":  ["Book", "Podcast", "Fundraising Campaign", "Retreat (Event)", "Subscription"]
    },
    {
        "key":         "blurb",
        "name":        "Blurb",
        "role":        "supporting",
        "description": "100–150 word promotional blurb for marketing.",
        "ai_generated": True,
        "work_types":  ["Book"]
    },
    {
        "key":         "tagline",
        "name":        "Tagline",
        "role":        "supporting",
        "description": "Punchy single-sentence chapter hook.",
        "ai_generated": True,
        "work_types":  ["Book"]
    },
    {
        "key":         "image_prompt",
        "name":        "Image Prompt",
        "role":        "supporting",
        "description": "Cinematic image generation prompt for the chapter header.",
        "ai_generated": True,
        "work_types":  ["Book"]
    },
    {
        "key":         "header_image",
        "name":        "Header Image",
        "role":        "supporting",
        "description": "Generated or uploaded chapter header image.",
        "ai_generated": False,
        "work_types":  ["Book"]
    },
    {
        "key":         "audio",
        "name":        "Audio",
        "role":        "supporting",
        "description": "Audio recording of the chapter or episode.",
        "ai_generated": False,
        "work_types":  ["Book", "Podcast"]
    },
]


def get_register():
    """Return the asset register, seeding defaults if the file doesn't exist yet."""
    data = read_json(ASSET_REGISTER_FILE)
    if data is None:
        write_json(ASSET_REGISTER_FILE, DEFAULT_ASSET_REGISTER)
        return DEFAULT_ASSET_REGISTER
    return data


def supporting_keys_for_work_type(work_type):
    """Return {key: 'missing'} dict for all supporting assets that apply to work_type."""
    register = get_register()
    return {
        a['key']: 'missing'
        for a in register
        if a.get('role') == 'supporting' and work_type in (a.get('work_types') or [])
    }


@bp.route('/api/asset-register', methods=['GET'])
def get_asset_register():
    return jsonify(get_register())


@bp.route('/api/asset-register', methods=['PUT'])
def update_asset_register():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({"error": "Asset register must be a JSON array"}), 400
    # Validate each entry has at least key, name, role
    for a in data:
        if not a.get('key') or not a.get('name') or not a.get('role'):
            return jsonify({"error": "Each asset must have key, name, and role"}), 400
    write_json(ASSET_REGISTER_FILE, data)
    return jsonify(data)
