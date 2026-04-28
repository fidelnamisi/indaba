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
    from routes.asset_register import supporting_keys_for_work_type
    data      = request.get_json()
    pipeline  = read_json('content_pipeline.json') or []
    work_type = data.get('work_type', 'Book')

    # Subscription is a CRM construct — it has no modules.
    NO_MODULE_TYPES = {'Subscription'}
    if work_type in NO_MODULE_TYPES:
        return jsonify({'error': f'{work_type} works do not have modules. Manage them via the CRM pipeline.'}), 400

    # Initialize supporting_assets from the Asset Register for this work type.
    # Merge: preserve any keys the caller explicitly sent, then fill in missing ones.
    sent_ps  = data.get('producing_status', {})
    sent_sa  = sent_ps.get('supporting_assets', {})
    register_sa = supporting_keys_for_work_type(work_type)
    # Register wins for keys not already in sent_sa
    merged_sa = {**register_sa, **sent_sa}

    # Auto-assign chapter_number if not provided
    chapter_number = data.get('chapter_number')
    if not chapter_number:
        book = data.get('book', '')
        chapter_number = max(
            (e.get('chapter_number') or 0 for e in pipeline if e.get('book') == book),
            default=0
        ) + 1

    entry = {
        'id':                str(uuid.uuid4()),
        'chapter':           data.get('chapter', ''),
        'book':              data.get('book', ''),
        'chapter_number':    chapter_number,
        'work_type':         work_type,
        'workflow_stage':    data.get('workflow_stage', 'producing'),
        'vip_group_status':  data.get('vip_group_status', 'not_started'),
        'patreon_status':    data.get('patreon_status', 'not_started'),
        'website_status':    data.get('website_status', 'not_started'),
        'wa_channel_status': data.get('wa_channel_status', 'not_started'),
        'assets':            data.get('assets', {}),
        'notes':             data.get('notes', ''),
        'producing_status':  {
            'essential_asset':  sent_ps.get('essential_asset', 'missing'),
            'supporting_assets': merged_sa,
        },
        'publishing_status':  data.get('publishing_status', {}),
        'promoting_status':   data.get('promoting_status', {}),
        'serializer_chunks':  data.get('serializer_chunks', []),
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


# ── Serializer chunks ────────────────────────────────────────────────────────

@bp.route('/api/content-pipeline/<entry_id>/serialize', methods=['POST'])
def serialize_module(entry_id):
    """
    AI-split the module's essential asset (prose) into delivery chunks.
    Accepts optional body: { num_chunks: int, target_words: int, append: bool }
    """
    import json as _json
    import re as _re
    from services.ai_service import call_ai
    from utils.constants import BOOK_SERIALIZER_FIXED_PROMPT

    body         = request.get_json() or {}
    num_chunks   = int(body.get('num_chunks', 3))
    target_words = int(body.get('target_words', 300))
    append_mode  = bool(body.get('append', False))

    pipeline = read_json('content_pipeline.json') or []
    entry = next((e for e in pipeline if e['id'] == entry_id), None)
    if not entry:
        return jsonify({'error': 'Not found'}), 404

    # Determine prose field based on work type
    PROSE_FIELD = {
        'Book':                 'prose',
        'Podcast':              'audio_notes',
        'Fundraising Campaign': 'campaign_narrative',
        'Retreat (Event)':      'event_offer',
        'Subscription':         'edition_content',
    }
    prose_key = PROSE_FIELD.get(entry.get('work_type', 'Book'), 'prose')
    prose = (entry.get('assets') or {}).get(prose_key, '').strip()
    if not prose:
        return jsonify({'error': f'No content found (looking for "{prose_key}"). Upload the essential asset first.'}), 400

    title             = entry.get('chapter', 'Untitled')
    existing_chunks   = entry.get('serializer_chunks', [])
    start_part        = (len(existing_chunks) + 1) if append_mode else 1

    system_prompt = BOOK_SERIALIZER_FIXED_PROMPT.format(
        work_title=title,
        start_part=start_part,
        num_chunks=num_chunks,
        target_words=target_words,
    )

    try:
        raw = call_ai('work_serializer', [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': f'Story text to split:\n\n{prose}'},
        ], max_tokens=4000)
    except Exception as e:
        return jsonify({'error': f'AI call failed: {e}'}), 500

    # Strip code fences if present
    clean = raw.strip()
    clean = _re.sub(r'^```(?:json)?\s*', '', clean, flags=_re.MULTILINE)
    clean = _re.sub(r'\s*```\s*$',       '', clean, flags=_re.MULTILINE)
    clean = clean.strip()

    try:
        data_json    = _json.loads(clean)
        segment_list = data_json.get('chunks', [])
    except Exception as e:
        return jsonify({'error': f'Could not parse AI response as JSON: {e}', 'raw': raw[:500]}), 500

    now    = datetime.utcnow().isoformat() + 'Z'
    chunks = []
    for c in segment_list:
        content = c.get('content', '').replace('\\n', '\n')
        chunks.append({
            'id':               str(uuid.uuid4()),
            'content':          content,
            'cliffhanger_note': c.get('cliffhanger_note', ''),
            'status':           'pending',
            'word_count':       len(content.split()),
            'created_at':       now,
            'message_id':       None,
        })

    # Save: replace or append
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            if append_mode:
                pipeline[i].setdefault('serializer_chunks', []).extend(chunks)
            else:
                pipeline[i]['serializer_chunks'] = chunks
            write_json('content_pipeline.json', pipeline)
            break

    saved = pipeline[next(j for j, e in enumerate(pipeline) if e['id'] == entry_id)]['serializer_chunks']
    return jsonify({'chunks': saved, 'count': len(saved)})


@bp.route('/api/content-pipeline/<entry_id>/serializer-chunks/<chunk_id>', methods=['PUT'])
def update_serializer_chunk(entry_id, chunk_id):
    """Update a single serializer chunk (status, content, etc.)."""
    data     = request.get_json() or {}
    pipeline = read_json('content_pipeline.json') or []
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            chunks = e.get('serializer_chunks', [])
            for j, c in enumerate(chunks):
                if c['id'] == chunk_id:
                    chunks[j] = {**c, **data, 'id': chunk_id}
                    pipeline[i]['serializer_chunks'] = chunks
                    write_json('content_pipeline.json', pipeline)
                    return jsonify(chunks[j])
            return jsonify({'error': 'Chunk not found'}), 404
    return jsonify({'error': 'Not found'}), 404


# ── Catalog Works (contentSchema — domain-model Works, not serializer Works) ──

import re as _re

@bp.route('/api/catalog-works', methods=['GET'])
def list_catalog_works():
    """Return all Works from catalog_works.json with their module counts.

    Query params:
      work_type=<type>   — filter to a specific work type (e.g. Subscription)
      has_modules=true   — only return works that support modules
    """
    catalog  = read_json('catalog_works.json') or {'works': []}
    pipeline = read_json('content_pipeline.json') or []

    wt_filter  = request.args.get('work_type', '').strip()
    has_modules_filter = request.args.get('has_modules', '').lower() == 'true'

    # Work types that do NOT have modules — Subscription is CRM-only
    NO_MODULE_TYPES = {'Subscription'}

    # Build module count per work code
    count_by_code = {}
    for e in pipeline:
        code = e.get('book', '')
        count_by_code[code] = count_by_code.get(code, 0) + 1

    works = []
    for w in catalog.get('works', []):
        wtype = w.get('work_type', '')
        if wt_filter and wtype != wt_filter:
            continue
        if has_modules_filter and wtype in NO_MODULE_TYPES:
            continue

        entry = dict(w)
        entry['has_modules']  = wtype not in NO_MODULE_TYPES
        entry['price']        = w.get('price', 0)
        entry['module_count'] = count_by_code.get(w['id'], 0)
        # Include the modules themselves for works that support them
        if entry['has_modules']:
            entry['modules'] = [
                {
                    'id':             e['id'],
                    'title':          e.get('chapter', ''),
                    'chapter_number': e.get('chapter_number', 0),
                    'workflow_stage': e.get('workflow_stage', 'producing'),
                    'website_status': e.get('website_status', 'not_started'),
                    'website_publish_info': e.get('website_publish_info'),
                    'has_prose':      bool((e.get('assets') or {}).get('prose', '').strip()),
                }
                for e in pipeline if e.get('book') == w['id']
            ]
            entry['modules'].sort(key=lambda m: m.get('chapter_number') or 0)
        else:
            entry['modules'] = []
        works.append(entry)

    return jsonify({'works': works})


@bp.route('/api/catalog-works', methods=['POST'])
def create_catalog_work():
    """
    Create a new Work in the catalog.
    For Book works: also registers the series in data/series_config.json.
    Body: { title, work_type, author, series_code, url_slug, genre,
            patreon_url, website_url, chapters_text (optional bulk import) }
    """
    data      = request.get_json() or {}
    title     = data.get('title', '').strip()
    work_type = data.get('work_type', 'Book').strip()

    if not title:
        return jsonify({'error': 'title is required'}), 400

    now      = datetime.utcnow().isoformat() + 'Z'
    catalog  = read_json('catalog_works.json') or {'works': []}

    if work_type == 'Book':
        series_code = data.get('series_code', '').strip().upper()
        url_slug    = data.get('url_slug', '').strip().lower()
        if not series_code:
            return jsonify({'error': 'series_code is required for Book works'}), 400
        if not url_slug:
            return jsonify({'error': 'url_slug is required for Book works'}), 400
        # Ensure unique code
        existing_ids = {w['id'] for w in catalog.get('works', [])}
        if series_code in existing_ids:
            return jsonify({'error': f'Series code {series_code} already exists'}), 409

        work_id = series_code

        # Register in series_config.json so the publisher can find it
        series_cfg = read_json('series_config.json') or {}
        abbrev     = series_code.lower()
        series_cfg[series_code] = {
            'name':       title,
            'slug':       url_slug,
            'abbrev':     abbrev,
            'genre':      data.get('genre', 'Fiction'),
            'series_url': f'/series/{url_slug}.html',
            'img_prefix': abbrev,
        }
        write_json('series_config.json', series_cfg)
    else:
        # Non-Book: generate a code from title
        code_base = _re.sub(r'[^A-Z0-9]', '_', title.upper())[:20].strip('_')
        work_id   = code_base
        series_code = None
        url_slug    = None

    new_work = {
        'id':          work_id,
        'code':        work_id,
        'title':       title,
        'work_type':   work_type,
        'author':      data.get('author', ''),
        'genre':       data.get('genre', ''),
        'url_slug':    url_slug or '',
        'patreon_url': data.get('patreon_url', ''),
        'website_url': data.get('website_url', ''),
        'created_at':  now,
    }
    if 'price' in data and data['price'] is not None:
        try:
            new_work['price'] = float(data['price'])
        except (ValueError, TypeError):
            pass
    catalog['works'].append(new_work)
    write_json('catalog_works.json', catalog)

    # Bulk import chapters if provided
    chapters_text = data.get('chapters_text', '').strip()
    imported = 0
    if chapters_text and work_type == 'Book':
        imported = _bulk_import_chapters(work_id, chapters_text)

    return jsonify({'work': new_work, 'chapters_imported': imported}), 201


def _bulk_import_chapters(work_code, text):
    """
    Parse text split by ## headings into pipeline entries.
    Format:
        ## Chapter Title
        Chapter prose...

        ## Next Chapter Title
        Next prose...
    Returns count of chapters imported.
    """
    pipeline = read_json('content_pipeline.json') or []
    now      = datetime.utcnow().isoformat() + 'Z'

    # Split on lines starting with ##
    raw_chapters = _re.split(r'\n(?=##\s)', text.strip())
    imported = 0
    chapter_number_start = max(
        (e.get('chapter_number', 0) for e in pipeline if e.get('book') == work_code),
        default=0
    ) + 1

    for i, chunk in enumerate(raw_chapters):
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.split('\n', 1)
        if not lines[0].startswith('##'):
            continue
        chapter_title = lines[0].lstrip('#').strip()
        prose         = lines[1].strip() if len(lines) > 1 else ''
        if not chapter_title:
            continue

        chapter_num = chapter_number_start + i
        entry_id    = f'{work_code.lower()}-ch{chapter_num}'

        entry = {
            'id':             entry_id,
            'work_type':      'Book',
            'book':           work_code,
            'chapter':        chapter_title,
            'chapter_number': chapter_num,
            'vip_group_status':   'not_started',
            'patreon_status':     'not_started',
            'website_status':     'not_started',
            'wa_channel_status':  'not_started',
            'workflow_stage':     'producing' if not prose else 'publishing',
            'producing_status': {
                'essential_asset': 'done' if prose else 'missing',
                'supporting_assets': {
                    'blurb':        'missing',
                    'tagline':      'missing',
                    'image_prompt': 'missing',
                    'header_image': 'missing',
                    'audio':        'missing',
                }
            },
            'publishing_status': {
                'vip_group':  'not_started',
                'patreon':    'not_started',
                'website':    'not_started',
                'wa_channel': 'not_started',
            },
            'promoting_status': {
                'wa_broadcast':    'not_sent',
                'email_excerpt':   'not_sent',
                'serializer_post': 'not_sent',
            },
            'assets': {
                'synopsis':           '',
                'blurb':              '',
                'tagline':            '',
                'image_prompt':       '',
                'prose':              prose,
                'author_note':        '',
                'header_image_path':  None,
                'audio': {
                    'local_path': None, 's3_url': None, 'audio_id': None,
                    'title': '', 'duration': '', 'min_tier': 1, 'uploaded_at': None,
                }
            },
            'notes':              '',
            'revision':           1 if prose else 0,
            'vip_group_revision': 0,
            'patreon_revision':   0,
            'website_revision':   0,
            'wa_channel_revision':0,
        }
        pipeline.append(entry)
        imported += 1

    if imported:
        write_json('content_pipeline.json', pipeline)
    return imported


@bp.route('/api/catalog-works/<work_id>', methods=['PUT'])
def update_catalog_work(work_id):
    """Update Work metadata (title, genre, patreon_url, website_url, author, price)."""
    data    = request.get_json() or {}
    catalog = read_json('catalog_works.json') or {'works': []}
    for i, w in enumerate(catalog.get('works', [])):
        if w['id'] == work_id:
            allowed = {'title', 'genre', 'patreon_url', 'website_url', 'author'}
            for k in allowed:
                if k in data:
                    catalog['works'][i][k] = data[k]
            if 'price' in data:
                try:
                    catalog['works'][i]['price'] = float(data['price']) if data['price'] is not None else None
                except (ValueError, TypeError):
                    pass
            write_json('catalog_works.json', catalog)
            return jsonify(catalog['works'][i])
    return jsonify({'error': 'Not found'}), 404


@bp.route('/api/catalog-works/<work_id>', methods=['DELETE'])
def delete_catalog_work(work_id):
    """Delete a Work from the catalog and all its pipeline modules."""
    catalog  = read_json('catalog_works.json') or {'works': []}
    pipeline = read_json('content_pipeline.json') or []
    catalog['works'] = [w for w in catalog.get('works', []) if w['id'] != work_id]
    pipeline         = [e for e in pipeline if e.get('book') != work_id]
    write_json('catalog_works.json', catalog)
    write_json('content_pipeline.json', pipeline)
    return jsonify({'ok': True})


@bp.route('/api/content-pipeline/<entry_id>', methods=['GET'])
def get_pipeline_entry(entry_id):
    pipeline = read_json('content_pipeline.json') or []
    for e in pipeline:
        if e['id'] == entry_id:
            return jsonify(e)
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
