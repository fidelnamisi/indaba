"""
Website publishing routes — publish chapters as static HTML to realmsandroads.com.
"""
import os
import shutil
import subprocess
from datetime import datetime, timezone

import werkzeug.utils
from flask import Blueprint, jsonify, request

from utils.json_store import read_json, write_json, DATA_DIR
from services.chapter_html_template import (
    get_series_config, derive_chapter_meta, get_prev_next, render_chapter_html,
)

bp = Blueprint('website_publisher', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_website_dir():
    """Return the configured website_dir, or None if not set."""
    settings = read_json('settings.json') or {}
    return settings.get('website', {}).get('website_dir', '').strip() or None


def _check_website_dir(website_dir):
    """Return (ok, error) after checking that chapters/ and img/ exist."""
    if not website_dir:
        return False, 'Website directory not configured. Set it in Settings → Website Publishing.'
    chapters_dir = os.path.join(website_dir, 'public', 'chapters')
    images_dir   = os.path.join(website_dir, 'public', 'img')
    if not os.path.isdir(chapters_dir):
        return False, f'chapters/ directory not found at {chapters_dir}'
    if not os.path.isdir(images_dir):
        return False, f'img/ directory not found at {images_dir}'
    return True, None


def _update_chapters_json(website_dir, entry, meta):
    """Add or update the chapter's entry in public/data/chapters.json."""
    chapters_json_path = os.path.join(website_dir, 'public', 'data', 'chapters.json')
    assets = entry.get('assets', {})
    series = meta['series']

    excerpt = (assets.get('tagline') or '').strip()
    if not excerpt:
        blurb = (assets.get('blurb') or '')
        excerpt = blurb.split('.')[0].strip() + '.' if blurb else ''

    new_entry = {
        'id':        meta['chapter_id'],
        'series':    series['name'],
        'genre':     series['genre'],
        'chapter':   f"Chapter {entry['chapter_number']}",
        'title':     entry['chapter'],
        'url':       meta['chapter_url'],
        'seriesUrl': series['series_url'],
        'excerpt':   excerpt,
        'tags':      [],
    }

    try:
        with open(chapters_json_path, 'r', encoding='utf-8') as f:
            import json as _json
            existing = _json.load(f)
    except (FileNotFoundError, ValueError):
        existing = []

    updated = False
    for i, item in enumerate(existing):
        if item.get('id') == new_entry['id']:
            existing[i] = new_entry
            updated = True
            break
    if not updated:
        existing.append(new_entry)

    import json as _json
    tmp_path = chapters_json_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        _json.dump(existing, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, chapters_json_path)


def _trigger_redeploy(website_dir):
    """Run redeploy.sh in the website directory (non-blocking)."""
    redeploy_script = os.path.join(website_dir, 'redeploy.sh')
    if not os.path.exists(redeploy_script):
        return {'ok': False, 'error': f'redeploy.sh not found at {redeploy_script}'}
    result = subprocess.run(
        ['bash', 'redeploy.sh'],
        cwd=website_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        return {'ok': False, 'error': result.stderr[:500]}
    return {'ok': True}


def _publish_one(entry_id, pipeline, settings):
    """
    Publish a single pipeline entry to the website.
    Returns dict: { ok, chapter_slug, html_path, image_copied, error }
    """
    entry = next((e for e in pipeline if e['id'] == entry_id), None)
    if not entry:
        return {'ok': False, 'error': f'Entry {entry_id} not found in pipeline'}

    book          = entry.get('book', '')
    assets        = entry.get('assets', {})
    series_config = get_series_config()

    # Validation
    if book not in series_config:
        return {'ok': False, 'error': f'Unknown series: {book}'}
    if not isinstance(entry.get('chapter_number'), int) or entry['chapter_number'] < 1:
        return {'ok': False, 'error': 'chapter_number must be a positive integer'}
    if not entry.get('chapter', '').strip():
        return {'ok': False, 'error': 'Chapter title is empty'}
    if not assets.get('blurb', '').strip():
        return {'ok': False, 'error': 'Blurb is required'}
    if not assets.get('tagline', '').strip():
        return {'ok': False, 'error': 'Tagline is required'}
    prose = assets.get('prose', '').strip()
    if not prose or len(prose) < 100:
        return {'ok': False, 'error': 'Prose must be at least 100 characters'}

    website_dir = settings.get('website', {}).get('website_dir', '').strip()
    ok, err = _check_website_dir(website_dir)
    if not ok:
        return {'ok': False, 'error': err}

    meta                 = derive_chapter_meta(entry)
    prev_entry, next_entry = get_prev_next(entry, pipeline)
    html_content         = render_chapter_html(entry, prev_entry, next_entry)

    chapter_slug = meta['chapter_slug']
    image_name   = meta['image_name']
    html_path    = os.path.join(website_dir, 'public', 'chapters', f'{chapter_slug}.html')
    img_dst      = os.path.join(website_dir, 'public', 'img', image_name)

    # Write HTML (atomic)
    tmp_html = html_path + '.tmp'
    try:
        with open(tmp_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        os.replace(tmp_html, html_path)
    except OSError as e:
        if os.path.exists(tmp_html):
            os.remove(tmp_html)
        return {'ok': False, 'error': f'Failed to write HTML: {e}'}

    # Copy header image (optional — failure is non-fatal)
    image_copied = False
    header_image_path = assets.get('header_image_path')
    if header_image_path and os.path.isfile(header_image_path):
        try:
            shutil.copy2(header_image_path, img_dst)
            image_copied = True
        except OSError:
            pass  # Image copy failure is non-fatal

    # Update chapters.json
    _update_chapters_json(website_dir, entry, meta)

    # Update pipeline entry — flat field (backward compat) + nested fields
    published_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    chapter_url  = meta['chapter_url']
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            pipeline[i]['website_status']   = 'live'
            pipeline[i]['website_revision'] = e.get('revision', 1)
            # Nested publishing_status (Phase 2 domain model)
            pub_status = dict(pipeline[i].get('publishing_status') or {})
            pub_status['website'] = 'live'
            pipeline[i]['publishing_status'] = pub_status
            # Rich publish info for UI display
            pipeline[i]['website_publish_info'] = {
                'status':       'live',
                'published_at': published_at,
                'chapter_url':  chapter_url,
            }
            break

    return {
        'ok':           True,
        'chapter_slug': chapter_slug,
        'html_path':    html_path,
        'image_copied': image_copied,
        'published_at': published_at,
        'chapter_url':  chapter_url,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@bp.route('/api/website/status', methods=['GET'])
def website_status():
    website_dir = _get_website_dir()
    ok, err = _check_website_dir(website_dir)
    if not ok:
        return jsonify({'ok': False, 'error': err})
    return jsonify({'ok': True, 'website_dir': website_dir})


@bp.route('/api/pipeline/<entry_id>/upload-image', methods=['POST'])
def upload_chapter_image(entry_id):
    """Accept an uploaded image, save it to data/generated_images/, update pipeline."""
    pipeline = read_json('content_pipeline.json') or []
    entry    = next((e for e in pipeline if e['id'] == entry_id), None)
    if not entry:
        return jsonify({'error': 'Not found'}), 404

    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'No file provided'}), 400

    ext      = os.path.splitext(werkzeug.utils.secure_filename(file.filename))[1] or '.jpg'
    filename = f'chapter_{entry_id}{ext}'
    save_dir = os.path.join(DATA_DIR, 'generated_images')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)
    file.save(save_path)

    entry['assets']['header_image_path'] = save_path
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            pipeline[i] = entry
            break
    write_json('content_pipeline.json', pipeline)
    return jsonify({'ok': True, 'path': save_path, 'filename': filename})


@bp.route('/api/website/publish', methods=['POST'])
def publish_chapter():
    """Publish one chapter to the website. Body: { entry_id }"""
    data     = request.get_json() or {}
    entry_id = data.get('entry_id', '').strip()
    if not entry_id:
        return jsonify({'ok': False, 'error': 'entry_id is required'}), 400

    pipeline = read_json('content_pipeline.json') or []
    settings = read_json('settings.json') or {}

    result = _publish_one(entry_id, pipeline, settings)
    if not result['ok']:
        return jsonify(result), 400

    # Save updated pipeline
    write_json('content_pipeline.json', pipeline)

    # Auto-deploy
    if settings.get('website', {}).get('auto_deploy'):
        website_dir = settings['website']['website_dir']
        _trigger_redeploy(website_dir)

    return jsonify(result)


@bp.route('/api/website/publish-batch', methods=['POST'])
def publish_batch():
    """
    Publish multiple chapters.
    Body: { entry_ids: [...] }
    Returns: { results: [ { entry_id, ok, error|null }, ... ] }
    """
    data      = request.get_json() or {}
    entry_ids = data.get('entry_ids', [])
    if not entry_ids:
        return jsonify({'results': []})

    pipeline = read_json('content_pipeline.json') or []
    settings = read_json('settings.json') or {}
    results  = []

    for entry_id in entry_ids:
        res    = _publish_one(entry_id, pipeline, settings)
        result = {'entry_id': entry_id, 'ok': res['ok']}
        if not res['ok']:
            result['error'] = res.get('error')
        results.append(result)

    # Save updated pipeline once after all publishes
    write_json('content_pipeline.json', pipeline)

    # Auto-deploy once at the end
    if settings.get('website', {}).get('auto_deploy'):
        website_dir = settings['website']['website_dir']
        _trigger_redeploy(website_dir)

    return jsonify({'results': results})


@bp.route('/api/website/deploy', methods=['POST'])
def deploy_website():
    """Trigger a website redeploy regardless of publish state."""
    website_dir = _get_website_dir()
    ok, err = _check_website_dir(website_dir)
    if not ok:
        return jsonify({'ok': False, 'error': err}), 400
    result = _trigger_redeploy(website_dir)
    return jsonify(result)
