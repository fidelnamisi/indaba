"""
Audio routes — browse local pCloud files and upload to S3 for streaming.
pCloud is mounted locally so no API calls are needed; files are on disk.
"""
import os
import re
import threading

import boto3
from flask import Blueprint, jsonify, request

from utils.json_store import read_json, write_json
from services.chapter_html_template import get_series_config

bp = Blueprint('audio', __name__)

S3_BUCKET = 'realmsandroads-audio-664112763115'
S3_REGION = 'us-east-1'
S3_BASE_URL = f'https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com'

# Upload progress store: { job_id: {state, progress, url, error} }
_upload_jobs = {}


def _mp3s_in_folder(folder):
    """Return list of .mp3 files in folder, sorted by name."""
    if not folder or not os.path.isdir(folder):
        return []
    files = [f for f in os.listdir(folder) if f.lower().endswith('.mp3')]
    files.sort()
    return files


def _resolve_series(work_id: str, series_config: dict):
    """Return (key, config) by key or by name field (case-insensitive)."""
    if work_id in series_config:
        return work_id, series_config[work_id]
    needle = work_id.lower().strip()
    for k, v in series_config.items():
        if v.get('name', '').lower().strip() == needle:
            return k, v
    return None, None


@bp.route('/api/audio/browse/<path:work_id>', methods=['GET'])
def browse_audio(work_id):
    """List MP3 files in the pCloud folder for a given work."""
    series_config = get_series_config()
    _, series = _resolve_series(work_id, series_config)
    if series is None:
        return jsonify({'error': f'Unknown work: {work_id}'}), 404

    folder = series.get('pcloud_folder', '')
    files  = _mp3s_in_folder(folder)

    return jsonify({
        'work_id': work_id,
        'folder':  folder,
        'files':   files,
    })


@bp.route('/api/audio/upload', methods=['POST'])
def upload_audio():
    """
    Upload a local pCloud MP3 to S3 and save the URL to the module.
    Body: { work_id, filename, module_id, chapter_number }
    Spawns a background thread; poll /api/audio/upload-status/<job_id> for progress.
    """
    data           = request.get_json() or {}
    work_id        = data.get('work_id', '').strip()
    filename       = data.get('filename', '').strip()
    module_id      = data.get('module_id', '').strip()
    chapter_number = data.get('chapter_number')

    if not work_id or not filename or not module_id:
        return jsonify({'error': 'work_id, filename, and module_id are required'}), 400

    series_config = get_series_config()
    _, series = _resolve_series(work_id, series_config)
    if series is None:
        return jsonify({'error': f'Unknown work: {work_id}'}), 404

    folder = series.get('pcloud_folder', '')
    if not folder or not os.path.isdir(folder):
        return jsonify({'error': f'pCloud folder not found: {folder}'}), 404

    local_path = os.path.join(folder, filename)
    if not os.path.isfile(local_path):
        return jsonify({'error': f'File not found: {filename}'}), 404

    # Canonical S3 key: series-slug/chapter-N.mp3
    s3_prefix = series.get('s3_prefix', series['slug'])
    n         = chapter_number or _guess_chapter_number(filename)
    s3_key    = f"{s3_prefix}/chapter-{n}.mp3" if n else f"{s3_prefix}/{filename}"
    s3_url    = f"{S3_BASE_URL}/{s3_key}"

    import uuid
    job_id = str(uuid.uuid4())[:8]
    _upload_jobs[job_id] = {'state': 'uploading', 'progress': 0, 'url': None, 'error': None}

    def _run():
        try:
            s3 = boto3.client('s3', region_name=S3_REGION)
            file_size = os.path.getsize(local_path)

            def _progress(bytes_transferred):
                pct = int(bytes_transferred / file_size * 100) if file_size else 0
                _upload_jobs[job_id]['progress'] = pct

            s3.upload_file(
                local_path, S3_BUCKET, s3_key,
                ExtraArgs={'ContentType': 'audio/mpeg'},
                Callback=_progress,
            )

            # Save S3 URL to pipeline entry
            pipeline = read_json('content_pipeline.json') or []
            for entry in pipeline:
                if entry['id'] == module_id:
                    entry.setdefault('assets', {})['audio'] = s3_url
                    ps = entry.setdefault('producing_status', {})
                    sa = ps.setdefault('supporting_assets', {})
                    sa['audio'] = 'done'
                    break
            write_json('content_pipeline.json', pipeline)

            _upload_jobs[job_id]['state']    = 'done'
            _upload_jobs[job_id]['progress'] = 100
            _upload_jobs[job_id]['url']      = s3_url

        except Exception as e:
            _upload_jobs[job_id]['state'] = 'error'
            _upload_jobs[job_id]['error'] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'job_id': job_id, 'ok': True, 's3_key': s3_key, 's3_url': s3_url})


@bp.route('/api/audio/upload-status/<job_id>', methods=['GET'])
def upload_status(job_id):
    job = _upload_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)


@bp.route('/api/audio/unlink/<module_id>', methods=['POST'])
def unlink_audio(module_id):
    """Remove the audio S3 URL from a module (does NOT delete from S3)."""
    pipeline = read_json('content_pipeline.json') or []
    for entry in pipeline:
        if entry['id'] == module_id:
            entry.setdefault('assets', {}).pop('audio', None)
            ps = entry.setdefault('producing_status', {})
            sa = ps.setdefault('supporting_assets', {})
            sa['audio'] = 'missing'
            break
    write_json('content_pipeline.json', pipeline)
    return jsonify({'ok': True})


def _guess_chapter_number(filename):
    """Extract chapter number from filename heuristically."""
    m = re.search(r'ch\s*(\d+)', filename, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r'chapter[-_\s]*(\d+)', filename, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None
