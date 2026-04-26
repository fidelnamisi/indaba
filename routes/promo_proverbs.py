"""
Promo proverbs routes — CRUD, bulk import, CSV export.
"""
import csv
import io
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, make_response, request
from utils.json_store import read_json, write_json
from utils.constants import PROMO_PROVERBS_FILE

bp = Blueprint('promo_proverbs', __name__)


@bp.route('/api/promo/proverbs', methods=['GET'])
def list_promo_proverbs():
    used_filter = request.args.get('used')
    data        = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverbs    = data.get("proverbs", [])
    if used_filter:
        is_used  = used_filter.lower() == 'true'
        proverbs = [p for p in proverbs if p.get('used', False) == is_used]
    return jsonify({"proverbs": proverbs})


@bp.route('/api/promo/proverbs', methods=['POST'])
def add_promo_proverb():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    new_p = {
        "id":         str(uuid.uuid4()),
        "text":       text,
        "origin":     data.get('origin', ''),
        "used":       False,
        "used_at":    None,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    proverbs_data["proverbs"].append(new_p)
    write_json(PROMO_PROVERBS_FILE, proverbs_data)
    return jsonify(new_p), 201


@bp.route('/api/promo/proverbs/<proverb_id>', methods=['PUT'])
def update_proverb(proverb_id):
    body          = request.get_json()
    data          = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverb = next((p for p in data["proverbs"] if p["id"] == proverb_id), None)
    if not proverb:
        return jsonify({"error": "Proverb not found"}), 404
    if "text" in body and body["text"].strip():
        proverb["text"] = body["text"].strip()
    if "origin" in body:
        proverb["origin"] = body["origin"].strip()
    if "used" in body:
        proverb["used"] = bool(body["used"])
        if not body["used"]:
            proverb["used_at"] = None
    proverb["updated_at"] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_PROVERBS_FILE, data)
    return jsonify(proverb)


@bp.route('/api/promo/proverbs/<proverb_id>', methods=['DELETE'])
def delete_proverb(proverb_id):
    data          = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverbs      = data.get("proverbs", [])
    original_len  = len(proverbs)
    data["proverbs"] = [p for p in proverbs if p["id"] != proverb_id]
    if len(data["proverbs"]) == original_len:
        return jsonify({"error": "Proverb not found"}), 404
    write_json(PROMO_PROVERBS_FILE, data)
    return jsonify({"ok": True})


@bp.route('/api/promo/proverbs/import_bulk', methods=['POST'])
def import_proverbs_bulk():
    data = request.get_json()
    ps   = data.get('proverbs', [])
    if not isinstance(ps, list) or not ps:
        return jsonify({"error": "proverbs must be a non-empty array"}), 400

    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    imported      = 0
    now           = datetime.utcnow().isoformat() + "Z"

    for p in ps:
        text = p.get('text', '').strip()
        if text:
            proverbs_data["proverbs"].append({
                "id":         str(uuid.uuid4()),
                "text":       text,
                "origin":     p.get('origin', ''),
                "used":       False,
                "used_at":    None,
                "created_at": now,
            })
            imported += 1

    if imported > 0:
        write_json(PROMO_PROVERBS_FILE, proverbs_data)
    return jsonify({"imported": imported})


@bp.route('/api/promo/proverbs/export', methods=['GET'])
def export_proverbs_csv():
    data     = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverbs = data.get("proverbs", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Text', 'Origin', 'Used', 'Used At', 'Created At'])
    for p in proverbs:
        writer.writerow([
            p.get('id'), p.get('text'), p.get('origin'),
            p.get('used'), p.get('used_at'), p.get('created_at'),
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=proverbs_export.csv"
    response.headers["Content-type"]        = "text/csv"
    return response
