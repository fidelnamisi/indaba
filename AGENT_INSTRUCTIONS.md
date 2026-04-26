# Indaba — Agent Implementation Instructions

## Your Persona

You are a **Senior Full-Stack Engineer and QA Lead** with 15+ years of experience. You do not cut corners. You do not skip tests. You do not leave TODO comments in place of real implementations. You read existing code thoroughly before touching anything. You verify every change works before moving on. You treat every edge case as a production risk.

**Working rules:**
- Read every file you are about to modify before editing it.
- After every significant change, run a syntax check or smoke test.
- Never break existing functionality. Every existing API endpoint must continue to work after your changes.
- If a migration is needed (data model changes), write and run the migration before touching the UI.
- At the end of each feature, write a test checklist and verify every item passes before moving on.
- If something is ambiguous, implement the most conservative, backward-compatible interpretation.

---

## Cloud Architecture Guardrails

- **Always follow Industry Standard Best Practices.** Avoid "shortcut" architectures (like public S3 URLs) for security and sync features. If a robust solution exists (e.g., S3 Pre-signed URLs), implement it first.
- **S3 Media Sync:** Never rely on Public S3 ACLs. Always use S3 Pre-signed URLs to share media between local and EC2. 
- **Reference:** See the **`s3_presigned_urls_ki.md`** Knowledge Item for the standard pattern.

---

## Project Overview

**Indaba** is a personal productivity and publishing dashboard for a professional writer.

- **Backend:** Python / Flask, port 5050, file: `app.py`
- **Frontend:** Vanilla JS (no framework), `static/app.js`
- **Styles:** `static/style.css`
- **Data:** JSON files in `data/` directory (atomic writes via `os.replace()`)
- **Existing data files:** `projects.json`, `content_pipeline.json`, `settings.json`, `daily_log.json`, `lead_measures.json`

All data files use **atomic writes**: write to a `.tmp` file, then `os.replace()`. Never write directly. This pattern is already in the codebase — follow it.

---

## Implementation Order

Implement in this exact order. Do not start Feature N+1 until Feature N passes its test checklist.

1. Feature 3 — Mark task as complete (smallest, lowest risk, good warm-up)
2. Feature 4 — Phase templates as Work Breakdown Structures
3. Feature 1 — Publishing Dashboard with revision tracking + navigation tabs
4. Feature 2 — Earnings Dashboard (manual entry)

---

## Feature 3: Mark Task as Complete

### What it does
Projects currently can only be deleted. Users need to mark a project as **complete** — removing it from the active queue but preserving it in an archive for reference.

### Data model change
Add two fields to every project object:
```json
"completed": false,
"completed_at": null
```

**Migration required:** Before changing any UI code, run a migration script that reads `projects.json`, adds `completed: false` and `completed_at: null` to any project that doesn't have these fields, and writes it back. Run this migration on app startup in `app.py` — add it to a `migrate()` function that is called once at boot.

### Backend changes (`app.py`)

Add a `migrate()` function that is called at the bottom of the file before `app.run()`:

```python
def migrate():
    # Migrate projects: add completed fields if missing
    projects = read_json('projects.json') or []
    changed = False
    for p in projects:
        if 'completed' not in p:
            p['completed'] = False
            changed = True
        if 'completed_at' not in p:
            p['completed_at'] = None
            changed = True
    if changed:
        write_json('projects.json', projects)
```

The existing `PUT /api/projects/<id>` already does a full merge (`{**p, **data}`), so no new endpoint is needed — the frontend just sends `{ completed: true, completed_at: <iso_timestamp> }`.

### Frontend changes (`app.js`)

**In `renderProjects()` (or wherever project cards are rendered):**

1. Split projects into two groups: `active` (completed === false) and `completed` (completed === true).
2. Render active projects exactly as before.
3. After the active projects in each priority tier, render a **collapsed "Completed" section** with a toggle button: `▸ Completed (N)`. Clicking it expands/collapses. Start collapsed.
4. Each completed project card is visually muted (reduced opacity, strikethrough on name). Show `completed_at` date. Show a **"Reopen"** button that sets `completed: false, completed_at: null`.

**Add a ✓ Complete button to active project cards:**
- Place it alongside the existing action buttons.
- On click: `confirm("Mark [project name] as complete?")` — if confirmed, call `PUT /api/projects/:id` with `{ completed: true, completed_at: new Date().toISOString() }`.
- On success: refresh the project list in state and re-render.

**Do not change** the delete behaviour. Completed and deleted are different.

### Test checklist — Feature 3
- [ ] App starts without errors after migration
- [ ] Existing projects all have `completed: false` in the JSON after migration
- [ ] Clicking ✓ Complete on a project moves it to the Completed section
- [ ] Completed project shows completion date
- [ ] Completed section starts collapsed; clicking toggle expands/collapses
- [ ] Clicking Reopen returns a completed project to the active queue
- [ ] Clicking Delete still works on both active and completed projects
- [ ] All other project functionality (phase, next action, notes, deadline) unchanged

---

## Feature 4: Phase Templates as Work Breakdown Structures

### What it does
Phase templates currently store a single string per project type (the default starting phase). This needs to change to an **ordered list of phases** — a full Work Breakdown Structure. When a project is created, it starts at Phase 1. Users can advance or retreat through phases from the project card.

### Data model change — `settings.json`

`phase_templates` values change from strings to arrays:

**Before:**
```json
"phase_templates": {
  "podcast": "Phase 1 - Find the topic."
}
```

**After:**
```json
"phase_templates": {
  "podcast": ["Find the topic", "Prepare topic", "Record", "Edit", "Publish", "Share"]
}
```

**Migration:** In the `migrate()` function (created in Feature 3), add logic to read `settings.json`, and for each key in `phase_templates`, if the value is a string (not an array), replace it with a single-item array containing that string. Write back.

### Settings UI — Phase Templates section (`app.js` → `openSettingsModal`)

Replace the current single `<input>` per project type with a **phase list editor**:

For each project type:
- Show the type label (e.g. "Podcast")
- Show an ordered list of existing phases. Each phase has:
  - The phase name (non-editable inline — to edit, delete and re-add)
  - An **↑** button (disabled if first item)
  - A **↓** button (disabled if last item)
  - A **✕** remove button
- Below the list: a text input + **"Add phase"** button to append a new phase to the list
- If the list is empty, show placeholder text: "No phases defined — add one below"

These changes are **staged in the DOM only** until the user clicks the main Settings "Save" button. On save, collect the current ordered list for each type from the DOM and write it to `settings.json` under `phase_templates`.

### Project card — phase navigation

On the project card, below the current phase display:

- If the project's type has a phase template with >1 phase:
  - Show **← Prev phase** button (disabled if at first phase or phase not found in template)
  - Show **→ Next phase** button (disabled if at last phase)
  - These buttons call `PUT /api/projects/:id` with the new phase name
  - If the user clicks Next Phase while on the **last phase**, show a confirm dialog: `"This is the last phase. Mark project as complete?"` — if confirmed, complete the project (same behaviour as Feature 3's Complete button)

- Phase display should show progress context: **"Phase 3 of 6 — Edit"** if the template is known, or just the phase name if not.

### `captureSubmit()` — new project creation

When creating a new project, if the selected type has a phase template:
- Auto-set `phase` to the first item in the template array
- If no template exists, leave phase blank as before

### Test checklist — Feature 4
- [ ] Migration converts existing string phase values to single-item arrays without data loss
- [ ] Settings modal shows ordered phase list for each project type
- [ ] Adding a phase appends it to the list
- [ ] Removing a phase removes it from the list
- [ ] ↑/↓ buttons reorder phases correctly; boundary buttons are disabled
- [ ] Saving settings writes the correct array structure to `settings.json`
- [ ] New project of a typed with a template auto-sets phase to first item
- [ ] Project card shows "Phase X of Y — Name" when template is known
- [ ] ← Prev and → Next buttons change the phase and re-render the card
- [ ] Next on last phase offers Complete confirmation
- [ ] Prev on first phase is disabled
- [ ] Project types with no template show no phase nav buttons (no regression)
- [ ] All existing project creation and editing still works

---

## Feature 1: Navigation Tabs + Publishing Dashboard + Revision Tracking

### What it does
The content pipeline currently lives in a cramped sidebar. This feature:
1. Adds a **top navigation tab bar** to the app: Dashboard | Publishing | Earnings
2. The **Dashboard** tab is the existing home view, but with the full pipeline table replaced by a compact 3-line summary widget
3. The **Publishing** tab is a new full-width view showing all chapters grouped by book, with revision tracking and publish actions
4. Revision tracking: each chapter tracks a master revision number and per-platform revision numbers, so you can see at a glance which platforms are stale after a revision

### Data model change — `content_pipeline.json`

Add these fields to every pipeline entry:

```json
"revision": 1,
"vip_group_revision": 0,
"patreon_revision": 0,
"website_revision": 0,
"wa_channel_revision": 0
```

**Rules:**
- `revision` = the current master revision of this chapter's content (starts at 1)
- `{platform}_revision` = the revision number that is currently live on that platform (0 = never published)
- A platform is **current** if `platform_revision === revision` AND `platform_status === "live"`
- A platform is **stale** if `platform_revision > 0 AND platform_revision < revision` (was live but revision has moved on)
- A platform is **never published** if `platform_revision === 0`

**Migration:** Add to `migrate()` in `app.py`:
- Read `content_pipeline.json`
- For each entry, if `revision` is missing, set it to `1`
- For each of the 4 platforms, if `{platform}_revision` is missing, set it to `0`
- Write back

### Backend changes (`app.py`)

The existing `PUT /api/content-pipeline/<entry_id>` already does a full merge, so no new endpoints are needed. The frontend sends whatever fields need updating.

Also add `content_pipeline` to the `/api/dashboard` response if it's not already there (verify this — it should already be present).

### Navigation tabs — HTML + JS

**In `index.html` (or wherever the main template is):** Add a `<nav class="app-nav">` element directly below the `<header>`:

```html
<nav class="app-nav" id="app-nav">
  <button class="nav-tab active" data-view="dashboard" onclick="switchView('dashboard')">Dashboard</button>
  <button class="nav-tab" data-view="publishing" onclick="switchView('publishing')">Publishing</button>
  <button class="nav-tab" data-view="earnings" onclick="switchView('earnings')">Earnings</button>
</nav>
```

**In `app.js`:** Add `state.activeView = 'dashboard'`.

Add `switchView(view)` function:
```javascript
function switchView(view) {
  state.activeView = view;
  document.querySelectorAll('.nav-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.view === view));
  document.getElementById('main').style.display = view === 'dashboard' ? '' : 'none';
  document.getElementById('publishing-view').style.display = view === 'publishing' ? '' : 'none';
  document.getElementById('earnings-view').style.display = view === 'earnings' ? '' : 'none';
  if (view === 'publishing') renderPublishingDashboard();
  if (view === 'earnings') renderEarningsDashboard();
}
```

**In HTML:** Add `<div id="publishing-view" style="display:none;"></div>` and `<div id="earnings-view" style="display:none;"></div>` alongside the existing `<div id="main">`.

### Dashboard sidebar — compact pipeline summary

Replace the full pipeline table in the sidebar with a compact summary widget:

```
CONTENT PIPELINE
RISE OF THE RAIN QUEEN   8 chapters   3 live · 5 pending
OUTLAWS AND OUTCASTS     9 chapters   0 live · 9 pending
MAN OF STONE AND SHADOW  36 chapters  0 live · 36 pending
Open Publishing Dashboard →
```

Each book row shows: book title, chapter count, how many are fully live (all 4 platforms live at current revision) vs how many have anything pending. "Open Publishing Dashboard →" is a link that calls `switchView('publishing')`.

Keep the "+ Add chapter" button in the summary widget so users can still quickly add entries without navigating.

### Publishing Dashboard view (`renderPublishingDashboard()`)

Full-width view (no sidebar). Layout:

**Header row:**
- Title: "Publishing Dashboard"
- Right side: "+ Add Chapter" button

**For each book (ROTRQ, OAO, MOSAS):** A section with:
- Book title as a section header (full name, chapter count)
- A table with columns: `Chapter | Rev | VIP Group | Patreon | Website | WA Channel | Actions`

**Each chapter row:**

`Chapter` — chapter name, clickable to expand asset drawer (same as current behaviour)

`Rev` — the master revision number displayed as `v1`, `v2`, etc. Plus a **⊕ Bump** button (small, subtle). Clicking Bump shows confirm: `"Mark '[chapter name]' as revised to v[N+1]? This will flag all live platforms as needing an update."` On confirm, sends `PUT /api/content-pipeline/:id` with `{ revision: current + 1 }` and re-renders.

`VIP Group`, `Patreon`, `Website`, `WA Channel` — each cell shows:
- A status badge (same STATUS_LABELS as existing: not started / in progress / pending / live)
- A small revision badge indicating which revision is live on that platform:
  - If `platform_revision === 0`: no badge (never published)
  - If `platform_revision === chapter.revision` AND status is live: green `v[N] ✓` badge
  - If `platform_revision > 0 AND platform_revision < chapter.revision`: amber `v[platform_revision] — needs update` badge
- A **Publish** button (visible on hover, or always visible — your call on UX). Clicking it:
  - Cycles the status to `live` AND sets `{platform}_revision` to the current `chapter.revision`
  - Sends one `PUT` call with both fields updated
  - Re-renders

The existing `cyclePipelineStatus()` function in `app.js` only updates the status field. **Do not remove it** — it is still used by the compact summary. But in the Publishing Dashboard, the Publish button should use a new dedicated function `publishChapterToPlatform(id, platform)` that updates both status and revision together.

`Actions` — "Edit Assets" button (opens existing edit modal).

**Asset drawer** (expanded row) — same as current implementation. No changes needed.

### Test checklist — Feature 1
- [ ] App starts without errors after migration
- [ ] All 53 pipeline entries have `revision: 1` and `{platform}_revision: 0` after migration
- [ ] Nav tabs render correctly; clicking each tab switches the view
- [ ] Dashboard tab shows existing home view unchanged
- [ ] Compact pipeline summary shows correct chapter counts per book
- [ ] "Open Publishing Dashboard →" navigates to Publishing tab
- [ ] Publishing view renders all 53 chapters grouped by 3 books
- [ ] Rev column shows correct revision numbers
- [ ] Platform cells show correct status badges
- [ ] Publish button sets status to live AND sets platform_revision to chapter.revision
- [ ] After publishing, green v[N] ✓ badge appears
- [ ] Bumping revision increments chapter.revision by 1
- [ ] After bump, previously-live platform cells show amber "v[N-1] — needs update" badge
- [ ] After re-publishing a stale platform, badge returns to green ✓
- [ ] Edit Assets modal still opens and saves correctly
- [ ] cyclePipelineStatus still works from the compact summary on Dashboard tab
- [ ] All existing app.js functions still work (no regressions)

---

## Feature 2: Earnings Dashboard (Manual Entry)

### What it does
A manual earnings tracker. Home sidebar shows the current month's total Patreon earnings. The Earnings tab shows a full history with monthly entries.

### New data file: `data/earnings.json`

Structure:
```json
{
  "2026-03": {
    "total_revenue": 0,
    "new_paid_subs": 0,
    "new_free_subs": 0,
    "cancellations": 0,
    "notes": ""
  }
}
```

Keys are `YYYY-MM` month strings. Values are the monthly metrics objects.

### Backend changes (`app.py`)

Add two new endpoints:

```python
@app.route('/api/earnings', methods=['GET'])
def get_earnings():
    return jsonify(read_json('earnings.json') or {})

@app.route('/api/earnings/<month>', methods=['PUT'])
def update_earnings(month):
    # month format: YYYY-MM — validate with regex before accepting
    import re
    if not re.match(r'^\d{4}-\d{2}$', month):
        return jsonify({'error': 'Invalid month format'}), 400
    data = request.get_json()
    earnings = read_json('earnings.json') or {}
    earnings[month] = {
        'total_revenue':  float(data.get('total_revenue', 0)),
        'new_paid_subs':  int(data.get('new_paid_subs', 0)),
        'new_free_subs':  int(data.get('new_free_subs', 0)),
        'cancellations':  int(data.get('cancellations', 0)),
        'notes':          str(data.get('notes', '')),
    }
    write_json('earnings.json', earnings)
    return jsonify(earnings[month])
```

Also add `earnings` to the `/api/dashboard` response:
```python
'earnings': read_json('earnings.json') or {}
```

And load it in `loadDashboard()` on the frontend: `state.earnings = d.earnings || {}`.

### Dashboard sidebar — earnings summary widget

In the sidebar, below Lead Measures, add a compact earnings widget:

```
PATREON — MARCH 2026
$450 this month   ↑ +$50 vs last month
```

- Pulls current month from `state.earnings`
- If no data for this month, shows `$0 — no data entered yet`
- Shows delta vs previous month (positive = green, negative = red, zero = neutral)
- "View earnings history →" link that calls `switchView('earnings')`

### Earnings Dashboard view (`renderEarningsDashboard()`)

Full-width view. Layout:

**Header:** "Earnings Dashboard" + "+ Add / Edit Month" button

**Summary bar at top:**
- Total YTD revenue
- Average monthly revenue (across months with data)
- Best month

**Bar chart (CSS-only, no external libraries):**
- One bar per month, height proportional to `total_revenue`
- Max height: 120px
- Bar colour: `var(--accent)` (`#E1B15A`)
- Month label below each bar
- Revenue amount above each bar
- If no data: show placeholder text "No earnings data yet — add your first month below"

**Monthly entries table** (most recent first):

| Month | Revenue | New Paid | New Free | Cancellations | Net Subs | Notes | Edit |
|-------|---------|----------|----------|---------------|----------|-------|------|

- `Net Subs` = `new_paid_subs - cancellations`
- `Edit` button opens an inline edit form (replaces the row with input fields + Save/Cancel)
- "+ Add Month" button at bottom adds a new row for the current month (if not already present) or lets you pick any YYYY-MM

**Edit form (inline row replacement):**
- Inputs for all 5 fields: total_revenue (number, 2 decimal places), new_paid_subs (integer), new_free_subs (integer), cancellations (integer), notes (text)
- Save calls `PUT /api/earnings/:month`
- Cancel reverts to display row

### Test checklist — Feature 2
- [ ] `earnings.json` is created as an empty object `{}` on first load if it doesn't exist
- [ ] `GET /api/earnings` returns correct data
- [ ] `PUT /api/earnings/2026-03` saves and returns correct data
- [ ] `PUT /api/earnings/invalid` returns 400
- [ ] Dashboard earnings widget shows current month total
- [ ] Delta calculation is correct (positive/negative/zero)
- [ ] "View earnings history →" navigates to Earnings tab
- [ ] Earnings tab renders without errors when no data exists
- [ ] Bar chart renders proportionally when data exists
- [ ] Adding a month entry saves to JSON and re-renders
- [ ] Editing an existing entry updates the values correctly
- [ ] Summary bar (YTD, average, best month) calculates correctly
- [ ] All other features unaffected by this addition

---

## General QA Requirements

After all four features are implemented:

1. **Start the server** (`python3 app.py`) and confirm it boots without errors or warnings.

2. **Run this smoke test sequence manually** (or script it with `curl`):
   - `GET /api/dashboard` — confirm response includes `projects`, `content_pipeline`, `earnings`, `settings`
   - `GET /api/earnings` — confirm returns `{}`  or existing data
   - `PUT /api/earnings/2026-03` with test data — confirm save
   - `PUT /api/projects/:id` with `{completed: true, completed_at: "..."}` — confirm updates
   - `PUT /api/content-pipeline/:id` with `{revision: 2}` — confirm updates
   - `GET /api/settings` — confirm `phase_templates` contains arrays, not strings

3. **Validate all JSON data files** after migration:
   ```python
   import json
   for f in ['projects.json', 'content_pipeline.json', 'settings.json', 'earnings.json']:
       with open(f'data/{f}') as fh:
           json.load(fh)  # Will raise if invalid
       print(f'{f}: valid')
   ```

4. **Check for JS errors** by loading the app in a browser and checking the console. Zero errors permitted.

5. **Confirm zero regressions** — every item in the original feature set must still work:
   - Create new project
   - Update project phase manually
   - Log session note
   - Add/edit chapter assets
   - Open Settings and save
   - Open Prompt Templates and view a prompt
   - Switch themes

---

## File Locations

```
/Users/fidelnamisi/Indaba/
├── app.py                          ← Flask backend
├── static/
│   ├── app.js                      ← Frontend JS
│   └── style.css                   ← Styles
├── data/
│   ├── projects.json               ← Projects data
│   ├── content_pipeline.json       ← Pipeline (53 entries)
│   ├── settings.json               ← Settings (includes asset_prompts, phase_templates)
│   ├── daily_log.json              ← Daily log
│   ├── lead_measures.json          ← Lead measure history
│   └── earnings.json               ← NEW — create if missing
└── templates/
    └── index.html                  ← Main HTML template
```

**Do not modify** `content_pipeline_backup.json` or `generated_assets.json` — these are source data files, not application files.

---

## Style Guide

Match the existing CSS variable system exactly:
- `var(--accent)` — gold highlight colour
- `var(--surface)`, `var(--surface2)` — card backgrounds
- `var(--bg)` — page background
- `var(--text)`, `var(--muted)`, `var(--muted2)` — text hierarchy
- `var(--border)`, `var(--border2)` — borders
- `var(--font-mono)` — monospace font

New UI elements must look native to the existing design. Do not introduce new font families, external icon libraries, or CSS frameworks.

Nav tabs: a simple horizontal row below the header, matching the dark/light theme. Active tab has `border-bottom: 2px solid var(--accent)` and `color: var(--accent)`. Inactive tabs use `var(--muted)`.
