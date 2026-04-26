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
    raw = settings.get('website', {}).get('website_dir', '')
    return raw.strip().strip("'\"") or None


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

    audio_url = (assets.get('audio') or '').strip() if isinstance(assets.get('audio'), str) else ''

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
    if audio_url:
        new_entry['audioUrl'] = audio_url

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


_deploy_status = {'state': 'idle', 'started_at': None, 'finished_at': None, 'error': None}


def _trigger_redeploy(website_dir):
    """Spawn redeploy.sh in the background; return immediately."""
    import threading
    redeploy_script = os.path.join(website_dir, 'redeploy.sh')
    if not os.path.exists(redeploy_script):
        return {'ok': False, 'error': f'redeploy.sh not found at {redeploy_script}'}

    def _run():
        _deploy_status['state']      = 'deploying'
        _deploy_status['started_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        _deploy_status['error']      = None
        try:
            result = subprocess.run(
                ['bash', 'redeploy.sh'],
                cwd=website_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                _deploy_status['state'] = 'deployed'
            else:
                _deploy_status['state'] = 'failed'
                _deploy_status['error'] = result.stderr[:500]
        except Exception as e:
            _deploy_status['state'] = 'failed'
            _deploy_status['error'] = str(e)
        finally:
            _deploy_status['finished_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    threading.Thread(target=_run, daemon=True).start()
    return {'ok': True, 'deploying': True}


def _update_toc(website_dir, series, first_entry):
    """
    Inject a new <section> block for 'series' into table-of-contents.html,
    immediately before the closing </main> tag, if the series is not already
    present. Writes atomically.
    """
    toc_path = os.path.join(website_dir, 'public', 'table-of-contents.html')
    if not os.path.exists(toc_path):
        return

    try:
        with open(toc_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return

    slug    = series['slug']
    abbrev  = series['abbrev']

    # Skip if already present
    if slug in content or f'id="{abbrev}-title"' in content:
        return

    name        = series['name']
    genre       = series['genre']
    synopsis    = series.get('synopsis', '')
    ch1_title   = first_entry.get('chapter', 'Chapter 1') if first_entry else 'Chapter 1'

    import html as _h
    name_esc     = _h.escape(name)
    genre_esc    = _h.escape(genre)
    synopsis_esc = _h.escape(synopsis, quote=False)
    ch1_esc      = _h.escape(ch1_title)

    new_section = f'''
    <!-- {name} -->
    <section class="toc-series-section" aria-labelledby="{abbrev}-title">
      <div class="toc-series-header">
        <span class="toc-series-genre">{genre_esc}</span>
        <h2 class="toc-series-title" id="{abbrev}-title">{name_esc}</h2>
        <span class="toc-chapter-count" id="toc-count-{abbrev}">New</span>
      </div>
      <p style="font-family:var(--font-ui);font-size:0.85rem;color:var(--text-muted-dark);margin-bottom:1.25rem;line-height:1.65;">{synopsis_esc}</p>
      <ol class="chapter-list" aria-label="{name_esc} chapters" id="toc-chapters-{abbrev}">
        <li class="chapter-list-item">
          <a href="/chapters/{slug}-chapter-1.html" rel="chapter">
            <span class="ch-num">Ch. 1</span>
            <span class="ch-title">{ch1_esc}</span>
            <span class="ch-meta">2026 &middot; Free</span>
          </a>
        </li>
      </ol>
      <div style="margin-top:1.25rem;">
        <a href="/series/{slug}.html" class="btn btn-secondary" style="padding:0.5rem 1.1rem;font-size:0.75rem;">Series Overview &rsaquo;</a>
      </div>
    </section>
'''

    # Insert before the anchor comment (which sits above the callout)
    anchor = '    <!-- NEW_SERIES_INSERTION_POINT -->'
    if anchor not in content:
        # Fallback: insert before </main>
        anchor = '  </main>'
        if anchor not in content:
            return

    updated = content.replace(anchor, new_section + anchor, 1)

    tmp_path = toc_path + '.tmp'
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(updated)
        os.replace(tmp_path, toc_path)
    except OSError:
        pass  # TOC update failure is non-fatal


def _update_homepage(website_dir, series, chapter_count=1):
    """
    Inject a new series card into the homepage (index.html) series grid,
    immediately before <!-- NEW_SERIES_CARD_END -->, if the series is not
    already present. Writes atomically.
    """
    index_path = os.path.join(website_dir, 'public', 'index.html')
    if not os.path.exists(index_path):
        return

    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return

    slug   = series['slug']
    anchor = '          <!-- NEW_SERIES_CARD_END -->'

    # Skip if already present or anchor missing
    if slug in content or anchor not in content:
        return

    import html as _h
    name_esc    = _h.escape(series['name'])
    genre_esc   = _h.escape(series['genre'])
    tagline_esc = _h.escape(series.get('tagline', series.get('synopsis', '')))
    img_prefix  = series.get('img_prefix', slug.replace('-', ''))
    ch_label    = f"{chapter_count} Chapter{'s' if chapter_count != 1 else ''} Available"

    new_card = f'''
          <article class="series-card">
            <div class="series-card-cover">
              <img src="/img/{img_prefix}-ch1-header.jpg" alt="{name_esc} — series cover" style="width:100%;height:100%;object-fit:cover;object-position:top;display:block;">
              <div class="series-genre-badge">{genre_esc}</div>
            </div>
            <div class="series-card-body">
              <h3 class="series-card-title">{name_esc}</h3>
              <p class="series-card-hook">{tagline_esc}</p>
              <div class="series-card-footer">
                <span class="series-chapter-count">{ch_label}</span>
                <a href="/chapters/{slug}-chapter-1.html" class="btn btn-primary" style="padding:0.55rem 1.1rem;font-size:0.75rem;">Start Series →</a>
              </div>
            </div>
          </article>

'''

    updated = content.replace(anchor, new_card + anchor, 1)

    tmp_path = index_path + '.tmp'
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(updated)
        os.replace(tmp_path, index_path)
    except OSError:
        pass  # Homepage update failure is non-fatal


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

    website_dir = settings.get('website', {}).get('website_dir', '').strip().strip("'\"")
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
    # header_image_path is stored as a URL like /data/images/header_<id>.jpg;
    # resolve it to the actual filesystem path.
    image_copied = False
    header_image_url = assets.get('header_image_path', '')
    if header_image_url:
        if header_image_url.startswith('/data/images/'):
            from utils.json_store import BASE_DIR as _BASE_DIR
            img_filename = header_image_url.split('/')[-1]
            header_image_fs = os.path.join(_BASE_DIR, 'data', 'generated_images', img_filename)
        else:
            header_image_fs = header_image_url  # legacy absolute path
        if os.path.isfile(header_image_fs):
            try:
                shutil.copy2(header_image_fs, img_dst)
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

    # Auto-generate series page if this is the first chapter for a new series
    series_page_path = os.path.join(website_dir, 'public', 'series', f"{meta['series']['slug']}.html")
    if not os.path.exists(series_page_path):
        from services.chapter_html_template import render_series_html
        series_html = render_series_html(meta['series'], entry)
        tmp_series = series_page_path + '.tmp'
        try:
            with open(tmp_series, 'w', encoding='utf-8') as f:
                f.write(series_html)
            os.replace(tmp_series, series_page_path)
        except OSError:
            pass  # Series page creation failure is non-fatal

        # Update table-of-contents.html and homepage to add the new series
        _update_toc(website_dir, meta['series'], entry)
        _update_homepage(website_dir, meta['series'], chapter_count=1)

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

    file = request.files.get('file') or request.files.get('image')
    if not file:
        return jsonify({'error': 'No file provided'}), 400

    ext      = os.path.splitext(werkzeug.utils.secure_filename(file.filename))[1] or '.jpg'
    filename = f'chapter_{entry_id}{ext}'
    save_dir = os.path.join(DATA_DIR, 'generated_images')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)
    file.save(save_path)

    image_url = f'/data/images/{filename}'
    entry.setdefault('assets', {})['header_image_path'] = image_url
    # Mark supporting asset as done
    ps = entry.setdefault('producing_status', {})
    sa = ps.setdefault('supporting_assets', {})
    sa['header_image'] = 'done'
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            pipeline[i] = entry
            break
    write_json('content_pipeline.json', pipeline)
    return jsonify({'ok': True, 'image_url': image_url, 'filename': filename})


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


@bp.route('/api/website/unpublish', methods=['POST'])
def unpublish_chapter():
    """Remove a published chapter from the website. Body: { entry_id }"""
    data     = request.get_json() or {}
    entry_id = data.get('entry_id', '').strip()
    if not entry_id:
        return jsonify({'ok': False, 'error': 'entry_id is required'}), 400

    pipeline = read_json('content_pipeline.json') or []
    entry = next((e for e in pipeline if e['id'] == entry_id), None)
    if not entry:
        return jsonify({'ok': False, 'error': 'Entry not found'}), 404

    website_dir = _get_website_dir()
    ok, err = _check_website_dir(website_dir)
    if not ok:
        return jsonify({'ok': False, 'error': err}), 400

    meta         = derive_chapter_meta(entry)
    chapter_slug = meta['chapter_slug']
    chapter_id   = meta['chapter_id']
    html_path    = os.path.join(website_dir, 'public', 'chapters', f'{chapter_slug}.html')

    # Remove HTML file
    if os.path.exists(html_path):
        os.remove(html_path)

    # Remove from chapters.json
    chapters_json_path = os.path.join(website_dir, 'public', 'data', 'chapters.json')
    try:
        import json as _json
        with open(chapters_json_path, 'r', encoding='utf-8') as f:
            chapters = _json.load(f)
        chapters = [c for c in chapters if c.get('id') != chapter_id]
        tmp = chapters_json_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            _json.dump(chapters, f, ensure_ascii=False, indent=2)
        os.replace(tmp, chapters_json_path)
    except (FileNotFoundError, ValueError):
        pass

    # Update pipeline entry
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            pipeline[i]['website_status'] = None
            pipeline[i]['website_publish_info'] = None
            pub_status = dict(pipeline[i].get('publishing_status') or {})
            pub_status.pop('website', None)
            pipeline[i]['publishing_status'] = pub_status
            break
    write_json('content_pipeline.json', pipeline)

    return jsonify({'ok': True, 'removed': html_path})


@bp.route('/api/website/work-sync/<work_id>', methods=['GET'])
def work_sync(work_id):
    """
    Compare what's in Indaba's pipeline with what's on the website filesystem.
    Returns per-chapter status for the given work_id (e.g. 'LB').
    """
    from services.chapter_html_template import get_series_config, derive_chapter_meta

    series_config = get_series_config()
    if work_id not in series_config:
        return jsonify({'ok': False, 'error': f'Unknown work: {work_id}'}), 404

    series    = series_config[work_id]
    slug      = series['slug']
    website_dir = _get_website_dir()

    pipeline  = read_json('content_pipeline.json') or []
    chapters  = [e for e in pipeline if e.get('book') == work_id
                 and isinstance(e.get('chapter_number'), int)]
    chapters.sort(key=lambda e: e['chapter_number'])

    # Read chapters.json from website to get what the web designer has published
    web_chapters = {}
    if website_dir:
        import json as _json
        cj_path = os.path.join(website_dir, 'public', 'data', 'chapters.json')
        try:
            with open(cj_path, 'r', encoding='utf-8') as f:
                for c in _json.load(f):
                    web_chapters[c.get('id')] = c
        except (FileNotFoundError, ValueError):
            pass

    result = []
    seen_ids = set()

    # Indaba chapters
    for entry in chapters:
        try:
            meta = derive_chapter_meta(entry)
        except Exception:
            continue
        chapter_id   = meta['chapter_id']
        chapter_slug = meta['chapter_slug']
        html_path    = os.path.join(website_dir, 'public', 'chapters', f'{chapter_slug}.html') if website_dir else None
        on_website   = bool(html_path and os.path.exists(html_path))

        pub_info     = entry.get('website_publish_info') or {}
        published_at = pub_info.get('published_at')
        chapter_url  = pub_info.get('chapter_url') or meta['chapter_url']

        # Check if on-disk file is newer than what Indaba last published
        #   (means web designer updated it outside Indaba)
        web_newer = False
        if on_website and published_at and html_path:
            file_mtime = datetime.fromtimestamp(os.path.getmtime(html_path), tz=timezone.utc)
            pub_dt     = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            web_newer  = file_mtime > pub_dt

        if on_website and not published_at:
            status = 'web_only'          # designer published, not through Indaba
        elif on_website and web_newer:
            status = 'web_newer'         # designer edited after Indaba published
        elif on_website:
            status = 'synced'
        else:
            status = 'not_published'

        seen_ids.add(chapter_id)
        result.append({
            'source':        'indaba',
            'entry_id':      entry['id'],
            'chapter_id':    chapter_id,
            'chapter_number': entry['chapter_number'],
            'title':         entry.get('chapter', ''),
            'status':        status,
            'published_at':  published_at,
            'chapter_url':   chapter_url,
            'on_website':    on_website,
        })

    # Web-only chapters (in chapters.json but not in Indaba pipeline)
    for cid, wc in web_chapters.items():
        if wc.get('series') == series['name'] and cid not in seen_ids:
            result.append({
                'source':     'website_only',
                'entry_id':   None,
                'chapter_id': cid,
                'title':      wc.get('title', ''),
                'status':     'web_only',
                'chapter_url': wc.get('url', ''),
                'on_website': True,
            })

    result.sort(key=lambda r: r.get('chapter_number') or 999)
    website_configured = bool(website_dir)
    return jsonify({'ok': True, 'work_id': work_id, 'series': series['name'],
                    'website_configured': website_configured, 'chapters': result})


@bp.route('/api/website/deploy-status', methods=['GET'])
def deploy_status():
    return jsonify(_deploy_status)


@bp.route('/api/website/deploy', methods=['POST'])
def deploy_website():
    """Trigger a website redeploy regardless of publish state."""
    website_dir = _get_website_dir()
    ok, err = _check_website_dir(website_dir)
    if not ok:
        return jsonify({'ok': False, 'error': err}), 400
    result = _trigger_redeploy(website_dir)
    return jsonify(result)
