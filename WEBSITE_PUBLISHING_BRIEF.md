# INDABA — WEBSITE PUBLISHING IMPLEMENTATION BRIEF
### Version 1.0 | March 2026 | For AI Coding Agent

---

## WHAT THIS BRIEF COVERS

Two features:

1. **Chapter Website Publishing** — from Indaba, press one button to publish a chapter (with its blurb, tagline, header image, and prose) as a static HTML file on realmsandroads.com. Includes single-chapter and bulk publish.

2. **Audio Publishing** — attach an audio narration file to a chapter in Indaba, upload it to S3, and register it with the website's audio API so subscribers can play it from their account page.

---

## ARCHITECTURE DECISION

The website is a **static site** deployed to AWS Amplify from the `/public` folder in the `realmsandroads.com` directory on this machine. There is no CMS API. Indaba and the website live on the same computer.

**The correct architecture is file-based:** Indaba generates static HTML files and writes them directly into the `realmsandroads.com/public/` directory. The user then triggers a redeploy from Indaba (which runs `bash redeploy.sh` in the website directory as a subprocess). No Lambda changes are required for chapter publishing.

Audio is different — it requires S3 upload and DynamoDB registration via the website's Lambda API. See Feature 2.

---

## WHAT EXISTS IN INDABA (do not break)

| Component | Location | Notes |
|-----------|----------|-------|
| Pipeline entries | `data/content_pipeline.json` | 53 chapters with blurb, tagline, image_prompt, synopsis |
| Pipeline CRUD | `routes/pipeline.py` | PUT already does full merge — extend, don't replace |
| S3 upload helper | `services/distribution_service.py` → `_upload_image_to_s3()` | Reuse for audio upload |
| Publishing tab (UI) | `static/app.js` → `renderPublishingDashboard()` | Add "Publish to Website" button here |
| Edit Assets modal | `static/app.js` | Add prose + author_note + header_image fields here |

## WHAT EXISTS IN THE WEBSITE (do not break)

| Component | Path | Notes |
|-----------|------|-------|
| Chapter HTML files | `public/chapters/{slug}.html` | 58 existing files; new ones must match this format exactly |
| Chapter header images | `public/img/{abbrev}-ch{N}-header.jpg` | Naming convention: `rotrq-ch1-header.jpg` |
| Search index | `public/data/chapters.json` | Array of objects; Indaba must update this when publishing |
| Redeploy script | `redeploy.sh` | Zips `public/` and uploads to Amplify |
| Lambda audio route | `lambda/routes/audio.js` | **Read this file before implementing Feature 2** |

---

## IMPLEMENTATION ORDER

1. Website Config in Settings (prerequisite for both features)
2. Data model migration (add prose, author_note, header_image_path fields)
3. Edit Assets modal UI update (let user enter prose + author_note)
4. Feature 1A: Single chapter publish to website
5. Feature 1B: Bulk publish (multiple chapters at once)
6. Feature 2: Audio upload and registration
7. QA

---

## PREREQUISITE: WEBSITE CONFIG IN SETTINGS

### What it is

Before Indaba can write files to the website, it needs to know where the website directory is on this machine. This is stored in `settings.json` under a new `website` key.

### Data model change (`settings.json`)

Add to `migrate()`:
```python
settings = read_json('settings.json') or {}
if 'website' not in settings:
    settings['website'] = {
        'website_dir': '',           # Absolute path to realmsandroads.com directory
        'auto_deploy': False,        # Whether to run redeploy.sh after publishing
    }
    write_json('settings.json', settings)
```

### Settings UI

In the Settings tab, add a new section **"Website Publishing"** with:
- A text input for **Website Directory** (absolute path, e.g. `/Users/fidelnamisi/realmsandroads.com`)
- A checkbox for **Auto-deploy after publishing**
- A **Test Connection** button that calls `GET /api/website/status` and shows a green tick if the directory exists and is writable, or a red error if not

### Backend route

```python
@app.route('/api/website/status', methods=['GET'])
def website_status():
    settings = read_json('settings.json') or {}
    website_dir = settings.get('website', {}).get('website_dir', '').strip()
    if not website_dir:
        return jsonify({'ok': False, 'error': 'Website directory not configured. Set it in Settings → Website Publishing.'})
    chapters_dir = os.path.join(website_dir, 'public', 'chapters')
    images_dir   = os.path.join(website_dir, 'public', 'img')
    if not os.path.isdir(chapters_dir):
        return jsonify({'ok': False, 'error': f'chapters/ directory not found at {chapters_dir}'})
    if not os.path.isdir(images_dir):
        return jsonify({'ok': False, 'error': f'img/ directory not found at {images_dir}'})
    return jsonify({'ok': True, 'website_dir': website_dir})
```

---

## MIGRATION: ADD PROSE + AUTHOR_NOTE + HEADER_IMAGE_PATH

Every pipeline entry's `assets` object needs three new fields.

### Add to `migrate()` in `app.py`

```python
pipeline = read_json('content_pipeline.json') or []
changed = False
for entry in pipeline:
    assets = entry.get('assets', {})
    if 'prose' not in assets:
        assets['prose'] = ''
        changed = True
    if 'author_note' not in assets:
        assets['author_note'] = ''
        changed = True
    if 'header_image_path' not in assets:
        assets['header_image_path'] = None
        changed = True
    entry['assets'] = assets
if changed:
    write_json('content_pipeline.json', pipeline)
```

### What each field holds

| Field | Type | Contents |
|-------|------|----------|
| `prose` | string | The full chapter text, as plain paragraphs separated by `\n\n`. No HTML. No markdown. Just paragraph breaks. |
| `author_note` | string | A short note from the author shown below the blurb on the chapter page. May be empty — if empty, the author note section is omitted. |
| `header_image_path` | string or null | Absolute path to the header image file on this machine (e.g. the output of the Imagen generation). Null if no image exists. |

---

## EDIT ASSETS MODAL — UI UPDATE

The existing Edit Assets modal in the Publishing tab must be extended to let the user enter these three new fields. Read the modal's current implementation in `app.js` before editing.

Add three new sections to the modal, in this order (after the existing fields):

### 1. Prose (chapter text)
- Label: `Chapter Text`
- Input: `<textarea>` — tall (min 300px), monospace font, full-width
- Placeholder: `Paste the chapter text here. Separate paragraphs with a blank line.`
- No character limit
- On load: populate from `assets.prose`
- On save: trim whitespace, store back

### 2. Author's Note
- Label: `Author's Note (optional)`
- Input: `<textarea>` — shorter (min 80px)
- Placeholder: `A brief note shown to readers before the chapter text. Leave blank to omit.`
- On load: populate from `assets.author_note`
- On save: trim whitespace, store back

### 3. Header Image
- Label: `Header Image`
- Show current value: if `header_image_path` is set, show the filename (not full path). If null, show "No image".
- Input: `<input type="file" accept="image/jpeg,image/png">` — lets user select an image file from their machine
- When a file is selected: call `POST /api/pipeline/{id}/upload-image` (multipart). On success, store the returned path in `assets.header_image_path` and update the displayed filename.
- **Do not move** the image yet — just store its path. The actual copy to `public/img/` happens at publish time.

### Backend route for image upload

```python
@app.route('/api/pipeline/<entry_id>/upload-image', methods=['POST'])
def upload_chapter_image(entry_id):
    """Accept an uploaded image file, save it to data/generated_images/, update pipeline entry."""
    import werkzeug
    pipeline = read_json('content_pipeline.json') or []
    entry = next((e for e in pipeline if e['id'] == entry_id), None)
    if not entry:
        return jsonify({'error': 'Not found'}), 404

    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'No file provided'}), 400

    # Derive safe filename from chapter id
    ext      = os.path.splitext(werkzeug.utils.secure_filename(file.filename))[1] or '.jpg'
    filename = f"chapter_{entry_id}{ext}"
    save_dir = os.path.join(DATA_DIR, 'generated_images')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)
    file.save(save_path)

    # Update pipeline entry
    entry['assets']['header_image_path'] = save_path
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            pipeline[i] = entry
            break
    write_json('content_pipeline.json', pipeline)
    return jsonify({'ok': True, 'path': save_path, 'filename': filename})
```

---

## FEATURE 1A: SINGLE CHAPTER PUBLISH TO WEBSITE

### What it does

Takes one pipeline entry and:
1. Validates that required fields are present (blurb, tagline, prose)
2. Generates the chapter HTML file
3. Copies the header image to `public/img/`
4. Updates `public/data/chapters.json` (the search index)
5. Updates the pipeline entry: `website_status = "live"`, `website_revision = entry.revision`
6. If `auto_deploy = True` in settings, runs `bash redeploy.sh`

### Series config (hardcode this in the service — it does not change)

```python
SERIES_CONFIG = {
    'ROTRQ': {
        'name':       'Rise of the Rain Queen',
        'slug':       'rise-of-the-rain-queen',
        'abbrev':     'rotrq',
        'genre':      'Epic Fantasy',
        'series_url': '/series/rise-of-the-rain-queen.html',
        'img_prefix': 'rotrq',
    },
    'OAO': {
        'name':       'Outlaws and Outcasts',
        'slug':       'outlaws-and-outcasts',
        'abbrev':     'oao',
        'genre':      'Epic Fantasy',
        'series_url': '/series/outlaws-and-outcasts.html',
        'img_prefix': 'oao',
    },
    'MOSAS': {
        'name':       'Man of Stone and Shadow',
        'slug':       'man-of-stone-and-shadow',
        'abbrev':     'mosas',
        'genre':      'Sci-Fi / Fantasy',
        'series_url': '/series/man-of-stone-and-shadow.html',
        'img_prefix': 'mosas',
    },
}
```

### Derived values (compute from the entry + series config)

```python
def derive_chapter_meta(entry):
    book       = entry['book']          # e.g. 'ROTRQ'
    series     = SERIES_CONFIG[book]
    n          = entry['chapter_number']
    abbrev     = series['abbrev']

    chapter_id   = f"{abbrev}-{n}"                                    # e.g. "rotrq-1"
    chapter_slug = f"{series['slug']}-chapter-{n}"                    # e.g. "rise-of-the-rain-queen-chapter-1"
    chapter_url  = f"/chapters/{chapter_slug}.html"
    image_name   = f"{abbrev}-ch{n}-header.jpg"                       # e.g. "rotrq-ch1-header.jpg"

    return {
        'chapter_id':   chapter_id,
        'chapter_slug': chapter_slug,
        'chapter_url':  chapter_url,
        'image_name':   image_name,
        'series':       series,
    }
```

### Prev/next navigation (compute from the full pipeline)

```python
def get_prev_next(entry, pipeline):
    """Return (prev_entry, next_entry) for same book, by chapter_number."""
    book      = entry['book']
    n         = entry['chapter_number']
    same_book = sorted([e for e in pipeline if e['book'] == book],
                       key=lambda e: e['chapter_number'])
    prev_e = next((e for e in same_book if e['chapter_number'] == n - 1), None)
    next_e = next((e for e in same_book if e['chapter_number'] == n + 1), None)
    return prev_e, next_e
```

### Prose → HTML paragraphs

```python
def prose_to_html(prose):
    """Convert plain prose (blank-line-separated paragraphs) to HTML <p> tags."""
    paras = [p.strip() for p in prose.strip().split('\n\n') if p.strip()]
    return '\n'.join(f'      <p>{p}</p>' for p in paras)
```

**Important:** Do NOT HTML-escape apostrophes, quotes, or dashes — the prose is plain text that the user has entered and it should render as-is. Do escape `<`, `>`, and `&` to prevent XSS.

```python
import html as _html
def escape_prose_char(text):
    return _html.escape(text, quote=False)
```

Apply `escape_prose_char` to each paragraph before wrapping in `<p>`.

### The HTML template

Create a new file `services/chapter_html_template.py` containing a single function `render_chapter_html(entry, prev_entry, next_entry)` that returns the full HTML string. The template must exactly match the structure of existing chapter pages. Do not use Jinja2 — use Python f-strings or string concatenation.

**Read `public/chapters/rise-of-the-rain-queen-chapter-1.html` in its entirety before writing this template.** The output must be byte-for-byte compatible with the existing format.

Key elements the template must produce:

```
1. DOCTYPE + <html lang="en">
2. <head>:
   - charset, viewport
   - <title>: "Chapter {N} — {chapter_title} | {series_name} — Realms and Roads"
   - meta description: "Chapter {N} — {chapter_title} — {series_name}. A {genre} story by Fidel Namisi..."
   - canonical URL: "https://realmsandroads.com/chapters/{chapter_slug}.html"
   - favicon + stylesheet links
   - GA4 script (copy exactly from existing files)
   - RSS + OG image meta tags (copy exactly from existing files)
   - JSON-LD schema (Chapter type, with series name and URL)
3. <body class="chapter-page" data-chapter-id="{chapter_id}" data-chapter-slug="{chapter_slug}">
4. Reading progress bar
5. Skip link
6. <nav> — standard site nav (copy from existing chapter files, use the same nav links)
7. <main id="main-content" class="site-main" data-chapter-id="{chapter_id}">
8. Header image block (if header_image_path is set):
      <div style="width:100%;max-height:420px;overflow:hidden;line-height:0;">
        <img src="/img/{image_name}" alt="Chapter {N} — {chapter_title}" ...>
      </div>
   If no header image: omit this block entirely.
9. <header class="chapter-header">:
   - series label with link: <div class="chapter-series-label"><a href="{series_url}" ...>{series_name}</a> · {genre}</div>
   - <h1 class="chapter-title-main">Chapter {N} — {chapter_title}</h1>
   - meta bar (By Fidel Namisi · 2026 · reading-time span)
10. Chapter toolbar (font size buttons + bookmark + share buttons) — copy from existing files
11. Top chapter nav (prev/next links):
    - If no prev: <span class="nav-prev-placeholder">← Beginning of Series</span>
    - If prev: <a href="/chapters/{prev_slug}.html" class="nav-prev">Ch.{prev_N} — {prev_title} ←</a>
    - Always: <a href="{series_url}" class="nav-toc-center">Series Overview</a>
    - If no next: nothing (omit next link)
    - If next: <a href="/chapters/{next_slug}.html" class="nav-next">Ch.{next_N} — {next_title} →</a>
12. Blurb block:
      <div class="chapter-blurb-block" ...>
        <p style="...color:var(--ancestral-gold)...">{tagline}</p>
        <p style="...color:var(--text-muted-dark)...">{blurb}</p>
      </div>
13. Author note (only if assets.author_note is non-empty):
      <aside class="author-note" aria-label="Author note">
        <div class="author-note-label">Author's Note</div>
        <p>{author_note}</p>
      </aside>
14. <article class="chapter-content" aria-label="Chapter text">
      {prose_html_paragraphs}
    </article>
15. Bottom chapter nav (same structure as top nav)
16. Comments section (copy from existing — links to Substack, always present)
17. </main>
18. <footer> — standard site footer (copy from existing chapter files)
19. Scripts: main.js, rr-auth.js, chapter-gate.js (in that order)
20. </body></html>
```

### Chapters.json update

`public/data/chapters.json` is the search index. When publishing a chapter, add or update the entry for that chapter. The structure is:

```json
{
  "id": "rotrq-1",
  "series": "Rise of the Rain Queen",
  "genre": "Epic Fantasy",
  "chapter": "Chapter 1",
  "title": "The Drum Thief",
  "url": "/chapters/rise-of-the-rain-queen-chapter-1.html",
  "seriesUrl": "/series/rise-of-the-rain-queen.html",
  "excerpt": "A one-sentence teaser (use the tagline if no excerpt is specified)",
  "tags": []
}
```

**Excerpt source:** Use `assets.tagline` as the excerpt (it's already a one-line hook). If tagline is empty, use the first sentence of `assets.blurb`.

**Tags:** Leave as empty array `[]` for now (tags can be added via the Admin panel on the website).

**Update logic:** Read `chapters.json`, find any existing entry with the same `id`, replace it. If not found, append. Write back.

### Backend route

Create a new Blueprint `routes/website_publisher.py`:

```python
@bp.route('/api/website/publish', methods=['POST'])
def publish_chapter():
    """
    Publish one chapter to the website.
    Body: { "entry_id": "rotrq-ch1" }
    """
```

**Validation (return 400 with human-readable error if any fail):**
- Entry exists in pipeline
- `entry['book']` is one of: ROTRQ, OAO, MOSAS
- `entry['chapter_number']` is an integer > 0
- `entry['chapter']` (title) is non-empty
- `assets['blurb']` is non-empty
- `assets['tagline']` is non-empty
- `assets['prose']` is non-empty and has at least 100 characters
- Website directory is configured and reachable (`GET /api/website/status` logic)

**Steps:**
1. Validate (above)
2. Call `derive_chapter_meta(entry)`
3. Get full pipeline to compute prev/next
4. Build HTML via `render_chapter_html(entry, prev_entry, next_entry)`
5. Write HTML to `{website_dir}/public/chapters/{chapter_slug}.html`
6. If `assets['header_image_path']` is set and the file exists: copy it to `{website_dir}/public/img/{image_name}` (using `shutil.copy2`)
7. Update `chapters.json`
8. Update pipeline entry: `website_status = "live"`, `website_revision = entry.get('revision', 1)`
9. If `settings.website.auto_deploy` is True: run `bash redeploy.sh` in `{website_dir}` as a subprocess (non-blocking, background)
10. Return `{ "ok": True, "chapter_slug": ..., "html_path": ..., "image_copied": bool }`

**Error handling:**
- Any file write failure: return `{"ok": False, "error": "..."}` with a human-readable message
- Never leave a partial publish — if HTML write succeeds but image copy fails, that's fine (image is optional). But if HTML write fails, roll back (delete the partial file if it was created).

### Frontend: "Publish to Website" button

In the Publishing tab (`renderPublishingDashboard()`), in the **Website** platform column for each chapter row:

- **Current behaviour:** shows a "Publish" button that cycles the status
- **New behaviour:** replace the status-cycling behaviour with a dedicated publish flow:
  - If `website_status !== 'live'`: show a **"Publish to Website"** button (gold outline)
  - If `website_status === 'live'` AND `website_revision === entry.revision`: show a green `v{N} ✓ Live` badge only (no button)
  - If `website_status === 'live'` AND `website_revision < entry.revision`: show amber `v{website_revision} — needs update` badge + **"Re-publish"** button

**On "Publish to Website" or "Re-publish" click:**
1. Disable the button, show spinner
2. Pre-validate client-side: if `assets.prose` is empty, show a toast error: `"Add chapter text first (Edit Assets → Chapter Text)"` — do not call API
3. Call `POST /api/website/publish` with `{ "entry_id": entry.id }`
4. On success: show toast `"Chapter published to website ✓"`, re-render the row
5. On error: show toast with the error message from the API response, re-enable the button

---

## FEATURE 1B: BULK PUBLISH

### What it does

Publishes multiple chapters at once. User selects which chapters to publish from the Publishing tab, clicks "Publish Selected to Website", and all are processed in sequence.

### Backend route

```python
@bp.route('/api/website/publish-batch', methods=['POST'])
def publish_batch():
    """
    Publish multiple chapters.
    Body: { "entry_ids": ["rotrq-ch1", "rotrq-ch2", ...] }
    Returns: { "results": [ { "entry_id": ..., "ok": bool, "error": str|null }, ... ] }
    """
```

Process each entry sequentially (not in parallel — avoid file write conflicts on `chapters.json`).

Collect results. Even if one fails, continue with the rest. Return the full results array.

Do NOT auto-deploy during batch — always wait until all are processed, then deploy once at the end if `auto_deploy` is True.

### Frontend

In the Publishing tab, add:
- A **checkbox** in the leftmost column of each chapter row (only shown for Website column — or as a row-level select-all)
- A **"Publish Selected to Website"** bulk action button in the table header (visible only when ≥1 checkbox is checked)
- After batch completes: show a summary toast: `"Published 4/6 chapters. 2 failed — check each row for details."`
- Rows that failed show a red error indicator

---

## FEATURE 2: AUDIO PUBLISHING

### Overview

When a chapter has an audio narration, Indaba should:
1. Accept an audio file upload (MP3/M4A)
2. Upload it to S3
3. Register it in the website's audio system (DynamoDB via the website Lambda)
4. Update the pipeline entry with audio metadata

### Before implementing: read the Lambda audio routes

**Read `lambda/routes/audio.js` in the `realmsandroads.com` directory** before writing any code for this feature. It contains the exact DynamoDB table name, field names, and API contract you need to match. Do not assume — read it first.

### Data model change (pipeline entry)

Add to `migrate()` — extend the `assets` object:
```python
if 'audio' not in assets:
    assets['audio'] = {
        'local_path':   None,   # Absolute path to the audio file on this machine
        's3_url':       None,   # S3 URL after upload
        'audio_id':     None,   # ID in the website's audio system (returned after registration)
        'title':        '',     # Display title (defaults to chapter title if blank)
        'duration':     '',     # Human-readable duration e.g. "34 min"
        'min_tier':     1,      # Minimum subscriber tier required (1 = The Traveller)
        'uploaded_at':  None,
    }
```

### Edit Assets modal — audio section

Add an "Audio" section to the Edit Assets modal:

- **Audio File**: show current filename if `audio.local_path` is set, else "No audio file".
  `<input type="file" accept="audio/mpeg,audio/mp4,audio/x-m4a">` with an Upload button
- **Title** (text input, pre-filled with chapter title)
- **Duration** (text input, e.g. "34 min")
- **Minimum Tier** (select: 0=Free, 1=Traveller, 2=Pathfinder, 3=Realm Keeper)
- **S3 Status**: show "Not uploaded", "Uploading…", or "Uploaded ✓" with the S3 URL (read-only)
- **Website Status**: show "Not registered", "Registered ✓" with the audioId (read-only)

### Backend routes for audio

```python
@bp.route('/api/audio/upload', methods=['POST'])
def upload_audio():
    """
    Accept an audio file and entry_id.
    1. Save the file to data/audio/{entry_id}{ext}
    2. Upload to S3 bucket (read bucket name from env: INDABA_S3_BUCKET or settings)
    3. Update pipeline entry with local_path + s3_url
    4. Return { "ok": True, "s3_url": "...", "local_path": "..." }
    """

@bp.route('/api/audio/register', methods=['POST'])
def register_audio():
    """
    Register an uploaded audio file with the website's Lambda API.
    Body: { "entry_id": "..." }

    1. Read the pipeline entry — must have s3_url set already
    2. Read the website's Lambda API base URL from settings (settings.website.lambda_api_url)
       e.g. "https://jk9fz38v33.execute-api.us-east-1.amazonaws.com"
    3. Call the appropriate Lambda endpoint (read lambda/routes/audio.js for the exact route)
    4. On success: update pipeline entry with audio.audio_id + uploaded_at
    5. Return { "ok": True, "audio_id": "..." }
    """
```

### Settings: Lambda API URL

Add to `settings.website` in the migration:
```python
settings['website']['lambda_api_url'] = 'https://jk9fz38v33.execute-api.us-east-1.amazonaws.com'
settings['website']['lambda_admin_email'] = ''   # The admin JWT email (for authenticated Lambda calls)
```

Show these fields in Settings → Website Publishing:
- **Lambda API URL** (text input, pre-filled with the above default)
- **Admin Email** (text input — must match the `ADMIN_EMAIL` env var set in the Lambda)

The admin email is needed because the Lambda's audio write endpoints are authenticated (they check the JWT). To call them from Indaba, Indaba needs to either:
a. Have a service-to-service shared secret, OR
b. Use the admin's JWT

**For now, implement option (b):** add a **Lambda Admin JWT** field in settings (a long text input). The user pastes their current JWT here. Indaba uses it as a Bearer token when calling the Lambda. Note in the UI that this JWT expires and will need refreshing.

### Audio publishing frontend

In the Publishing tab, add an **Audio** column to the chapter table (or expand the existing layout). Each row shows:
- If no audio: `—` with an "Add Audio" button
- If audio registered: `▶ Audio ✓` badge
- If audio uploaded but not registered: `S3 ✓ — needs registration` badge with "Register" button

---

## SETTINGS: ADDITIONAL FIELDS NEEDED

Add to `settings.website` in migration and Settings UI:

| Field | Type | Description |
|-------|------|-------------|
| `website_dir` | string | Absolute path to realmsandroads.com directory |
| `auto_deploy` | bool | Run redeploy.sh after publish |
| `lambda_api_url` | string | Website Lambda base URL |
| `lambda_admin_jwt` | string | Admin JWT for Lambda auth (refresh periodically) |

---

## DEPLOY TRIGGER (OPTIONAL BUT IMPORTANT)

If `auto_deploy` is True, after publishing run:

```python
import subprocess, os

def trigger_redeploy(website_dir):
    """Run redeploy.sh in the website directory. Non-blocking."""
    redeploy_script = os.path.join(website_dir, 'redeploy.sh')
    if not os.path.exists(redeploy_script):
        return {'ok': False, 'error': f'redeploy.sh not found at {redeploy_script}'}
    result = subprocess.run(
        ['bash', 'redeploy.sh'],
        cwd=website_dir,
        capture_output=True,
        text=True,
        timeout=300
    )
    if result.returncode != 0:
        return {'ok': False, 'error': result.stderr[:500]}
    return {'ok': True}
```

In the Publishing tab, also show a **"Deploy Website"** button (always visible, bottom of the view) that calls `POST /api/website/deploy` even without publishing — useful when the user has deployed from outside Indaba and wants to confirm the site is current.

---

## FILE LOCATIONS SUMMARY

### New files to create in Indaba

```
routes/website_publisher.py         — Flask Blueprint with publish + deploy routes
routes/audio_publisher.py           — Flask Blueprint with audio upload + register routes
services/chapter_html_template.py   — render_chapter_html() function
```

### Files to modify in Indaba

```
app.py              — register new blueprints + migrate() additions
static/app.js       — Edit Assets modal + Publishing tab + Settings UI
data/settings.json  — website config added by migrate()
data/content_pipeline.json — assets extended by migrate()
```

### Files to modify in the website

```
public/chapters/{new-slug}.html     — generated and written by Indaba
public/img/{new-image-name}.jpg     — copied from Indaba's generated_images/
public/data/chapters.json           — updated by Indaba at publish time
```

---

## TEST CHECKLIST — FEATURE 1 (Website Publishing)

- [ ] App starts without errors after migration
- [ ] All 53 pipeline entries have `prose`, `author_note`, `header_image_path` fields after migration
- [ ] Settings → Website Publishing shows all config fields
- [ ] Test Connection button returns success when website_dir is correctly set
- [ ] Test Connection button returns error when website_dir is wrong
- [ ] Edit Assets modal shows Prose textarea, Author's Note textarea, Header Image upload
- [ ] Saving prose in Edit Assets persists to content_pipeline.json
- [ ] Uploading an image via Edit Assets stores the path in assets.header_image_path
- [ ] Publish to Website fails with clear error if prose is empty
- [ ] Publish to Website fails with clear error if blurb is empty
- [ ] Publish to Website fails with clear error if website_dir is not configured
- [ ] Publish to Website succeeds and creates HTML file in the correct location
- [ ] Generated HTML has correct chapter_id, chapter_slug on body tag
- [ ] Generated HTML has correct series name, genre, prev/next nav links
- [ ] Generated HTML has blurb and tagline in the blurb block
- [ ] Generated HTML has prose rendered as `<p>` tags
- [ ] Generated HTML includes author_note section if non-empty
- [ ] Generated HTML omits author_note section if empty
- [ ] Generated HTML includes header image if header_image_path is set
- [ ] Generated HTML omits image block if header_image_path is null
- [ ] Header image is copied to public/img/ with correct naming convention
- [ ] chapters.json is updated with the new/updated entry
- [ ] Pipeline entry website_status is set to "live"
- [ ] Pipeline entry website_revision is set to the chapter's current revision
- [ ] Re-publishing an existing chapter overwrites the HTML (not duplicate)
- [ ] Bulk publish processes all selected entries, collects results
- [ ] Bulk publish continues if one entry fails
- [ ] Bulk publish summary toast shows correct success/failure count
- [ ] All existing Publishing tab functionality still works (status badges, Edit Assets modal for existing fields)

## TEST CHECKLIST — FEATURE 2 (Audio)

- [ ] All 53 pipeline entries have `assets.audio` object after migration
- [ ] Edit Assets modal shows Audio section with all fields
- [ ] Audio file upload saves to `data/audio/` and returns local_path
- [ ] S3 upload sends the file to the correct bucket and returns a URL
- [ ] Register audio calls the correct Lambda endpoint with correct fields
- [ ] Lambda registration returns an audio_id that is stored in the pipeline
- [ ] Audio column in Publishing tab shows correct badge states
- [ ] All existing functionality unaffected

---

## GENERAL ENGINEERING NOTES

1. **Read before you write.** Read every file you modify before touching it. Read `rise-of-the-rain-queen-chapter-1.html` and `outlaws-and-outcasts-chapter-1.html` in full before writing the HTML template.

2. **The HTML template is the most critical piece.** A malformed chapter page breaks the reading experience. After generating your first HTML file, open it in a browser and compare it visually to an existing chapter page before proceeding.

3. **Atomic writes everywhere.** All writes to JSON files use the existing `write_json()` helper which does atomic `os.replace()`. Do not write JSON files directly.

4. **Never break existing pipeline data.** The `migrate()` function must be additive only. It adds new fields with safe defaults — it never removes or renames existing fields.

5. **Prose encoding.** The prose text entered by the user is plain text. Escape `<`, `>`, `&` before inserting into HTML. Do not escape apostrophes or quotes (they render fine as-is in HTML body text).

6. **Prev/next links must always be accurate.** Before publishing chapter N, check that chapters N-1 and N+1 actually exist in the pipeline. If N-1 or N+1 has already been published, their HTML files will also need their nav links updated. However, for the initial implementation, only generate the correct prev/next for the chapter being published — do not retroactively re-publish neighbors. Add a note in the UI: "After publishing multiple chapters, re-publish earlier chapters to update their 'Next Chapter' links."

7. **chapters.json is append/update, never replace.** Read the full file, find and update the matching entry by `id`, write back. Never overwrite the whole file from scratch — that would delete entries for the other series.
