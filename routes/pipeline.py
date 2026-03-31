"""
Content pipeline and notes routes.
"""
import os
import glob
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request
from utils.json_store import read_json, write_json
from utils.constants import NOTES_DIR

bp = Blueprint('pipeline', __name__)


# ── Content pipeline ──────────────────────────────────────────────────────────

@bp.route('/api/content-pipeline', methods=['GET'])
def get_content_pipeline():
    return jsonify(read_json('content_pipeline.json') or [])


@bp.route('/api/content-pipeline', methods=['POST'])
def add_pipeline_entry():
    data     = request.get_json()
    pipeline = read_json('content_pipeline.json') or []
    entry    = {
        'id':                str(uuid.uuid4()),
        'chapter':           data.get('chapter', ''),
        'vip_group_status':  data.get('vip_group_status', 'not_started'),
        'patreon_status':    data.get('patreon_status', 'not_started'),
        'website_status':    data.get('website_status', 'not_started'),
        'wa_channel_status': data.get('wa_channel_status', 'not_started'),
        'assets':            data.get('assets', {}),
        'notes':             data.get('notes', ''),
    }
    pipeline.append(entry)
    write_json('content_pipeline.json', pipeline)
    return jsonify(entry), 201


@bp.route('/api/content-pipeline/<entry_id>', methods=['PUT'])
def update_pipeline_entry(entry_id):
    data     = request.get_json()
    pipeline = read_json('content_pipeline.json') or []
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            pipeline[i] = {**e, **data, 'id': entry_id}
            write_json('content_pipeline.json', pipeline)
            return jsonify(pipeline[i])
    return jsonify({'error': 'Not found'}), 404


@bp.route('/api/content-pipeline/<entry_id>/increment-revision', methods=['POST'])
def increment_revision(entry_id):
    data     = request.get_json() or {}
    field    = data.get('field', 'revision')
    delta    = data.get('delta', 1)
    pipeline = read_json('content_pipeline.json') or []
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            e[field]    = e.get(field, 0) + delta
            pipeline[i] = e
            write_json('content_pipeline.json', pipeline)
            return jsonify(pipeline[i])
    return jsonify({'error': 'Not found'}), 404


@bp.route('/api/content-pipeline/<entry_id>', methods=['DELETE'])
def delete_pipeline_entry(entry_id):
    pipeline = read_json('content_pipeline.json') or []
    write_json('content_pipeline.json', [e for e in pipeline if e['id'] != entry_id])
    return jsonify({'ok': True})


@bp.route('/api/content-pipeline/<entry_id>/workflow-stage', methods=['PUT'])
def set_workflow_stage(entry_id):
    """Move a module to a different workflow stage (producing/publishing/promoting)."""
    data     = request.get_json()
    stage    = data.get('stage', '')
    if stage not in ('producing', 'publishing', 'promoting'):
        return jsonify({'error': 'Invalid stage'}), 400
    pipeline = read_json('content_pipeline.json') or []
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            pipeline[i]['workflow_stage'] = stage
            write_json('content_pipeline.json', pipeline)
            return jsonify(pipeline[i])
    return jsonify({'error': 'Not found'}), 404


@bp.route('/api/content-pipeline/<entry_id>/producing-status', methods=['PUT'])
def update_producing_status(entry_id):
    """Update individual producing_status fields (essential_asset or supporting asset keys)."""
    data     = request.get_json()
    pipeline = read_json('content_pipeline.json') or []
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            ps = e.get('producing_status', {})
            if 'essential_asset' in data:
                ps['essential_asset'] = data['essential_asset']
            if 'supporting_assets' in data:
                ps.setdefault('supporting_assets', {}).update(data['supporting_assets'])
            pipeline[i]['producing_status'] = ps
            write_json('content_pipeline.json', pipeline)
            return jsonify(pipeline[i])
    return jsonify({'error': 'Not found'}), 404


@bp.route('/api/content-pipeline/<entry_id>/publishing-status', methods=['PUT'])
def update_publishing_status(entry_id):
    """Update per-platform publishing_status for a module."""
    data     = request.get_json()
    pipeline = read_json('content_pipeline.json') or []
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            ps = e.get('publishing_status', {})
            ps.update(data)
            pipeline[i]['publishing_status'] = ps
            write_json('content_pipeline.json', pipeline)
            return jsonify(pipeline[i])
    return jsonify({'error': 'Not found'}), 404


# ── Notes ─────────────────────────────────────────────────────────────────────

@bp.route('/api/notes', methods=['GET'])
def list_notes():
    os.makedirs(NOTES_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(NOTES_DIR, '*.md')),
                   key=os.path.getmtime, reverse=True)
    notes = []
    for f in files:
        name  = os.path.basename(f)
        mtime = datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        with open(f, 'r', encoding='utf-8') as fh:
            first = fh.readline().strip().lstrip('#').strip()
        notes.append({'filename': name, 'title': first or name, 'modified': mtime})
    return jsonify(notes)


@bp.route('/api/notes', methods=['POST'])
def create_note():
    data    = request.get_json()
    title   = data.get('title', 'Untitled').strip()
    content = data.get('content', '').strip()
    os.makedirs(NOTES_DIR, exist_ok=True)
    slug     = ''.join(c if c.isalnum() or c in '-_ ' else '' for c in title)
    slug     = slug.strip().replace(' ', '-').lower()[:40] or 'note'
    ts       = datetime.now().strftime('%Y%m%d-%H%M')
    filename = f'{ts}-{slug}.md'
    path     = os.path.join(NOTES_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'# {title}\n\n{content}')
    return jsonify({'filename': filename, 'title': title}), 201


@bp.route('/api/notes/<filename>', methods=['GET'])
def read_note(filename):
    filename = os.path.basename(filename)
    path     = os.path.join(NOTES_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'filename': filename, 'content': content})


@bp.route('/api/notes/<filename>', methods=['PUT'])
def update_note(filename):
    filename = os.path.basename(filename)
    path     = os.path.join(NOTES_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    content  = request.get_json().get('content', '')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return jsonify({'ok': True})


@bp.route('/api/notes/<filename>', methods=['DELETE'])
def delete_note(filename):
    filename = os.path.basename(filename)
    path     = os.path.join(NOTES_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({'ok': True})
