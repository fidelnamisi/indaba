"""
Promo settings routes.
"""
import uuid
from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json
from utils.constants import PROMO_SETTINGS_FILE, DEFAULT_PROMO_SETTINGS

bp = Blueprint('promo_settings', __name__)


@bp.route('/api/promo/settings', methods=['GET'])
def get_promo_settings():
    return jsonify(read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS)


@bp.route('/api/promo/settings', methods=['PUT'])
def update_promo_settings():
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Settings must be a JSON object"}), 400
    # Preserve serializer_profiles if not included in the PUT body
    existing = read_json(PROMO_SETTINGS_FILE) or {}
    if 'serializer_profiles' not in data and 'serializer_profiles' in existing:
        data['serializer_profiles'] = existing['serializer_profiles']
    write_json(PROMO_SETTINGS_FILE, data)
    return jsonify(data)


# ── Serializer Profile CRUD ───────────────────────────────────────────────────

def _get_profiles():
    settings = read_json(PROMO_SETTINGS_FILE) or {}
    return settings.get('serializer_profiles') or []

def _save_profiles(profiles):
    settings = read_json(PROMO_SETTINGS_FILE) or {}
    settings['serializer_profiles'] = profiles
    write_json(PROMO_SETTINGS_FILE, settings)


@bp.route('/api/serializer/profiles', methods=['GET'])
def list_profiles():
    return jsonify(_get_profiles())


@bp.route('/api/serializer/profiles', methods=['POST'])
def create_profile():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    profile = {
        "id":           str(uuid.uuid4()),
        "name":         name,
        "num_chunks":   data.get('num_chunks'),   # None = auto
        "target_words": int(data.get('target_words') or 200),
    }
    profiles = _get_profiles()
    profiles.append(profile)
    _save_profiles(profiles)
    return jsonify(profile), 201


@bp.route('/api/serializer/profiles/<profile_id>', methods=['PUT'])
def update_profile(profile_id):
    data     = request.get_json() or {}
    profiles = _get_profiles()
    idx      = next((i for i, p in enumerate(profiles) if p['id'] == profile_id), None)
    if idx is None:
        return jsonify({"error": "Profile not found"}), 404
    p = profiles[idx]
    if 'name'         in data: p['name']         = data['name']
    if 'num_chunks'   in data: p['num_chunks']   = data['num_chunks']   # allow None
    if 'target_words' in data: p['target_words'] = int(data['target_words'] or 200)
    profiles[idx] = p
    _save_profiles(profiles)
    return jsonify(p)


@bp.route('/api/serializer/profiles/<profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    profiles = _get_profiles()
    profiles = [p for p in profiles if p['id'] != profile_id]
    _save_profiles(profiles)
    return jsonify({"ok": True})
