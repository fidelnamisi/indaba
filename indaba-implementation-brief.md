# INDABA — EXTENDED IMPLEMENTATION BRIEF
### Version 1.0 | March 2026 | For AI Coding Assistant

---

# SECTION 1 — SYSTEM CONTEXT

## 1.1 What Indaba Is

Indaba is a self-hosted personal productivity and publishing command centre for a single user: a professional writer, ghostwriter, and content creator based in South Africa. It runs on a local machine. There is no authentication, no multi-user support, no database.

**Stack:**
- Backend: Python 3, Flask, port 5050 (auto-increments on conflict)
- Frontend: Vanilla JavaScript (state-driven rendering), HTML5, CSS3
- Storage: flat JSON files in `/data`, written atomically via `os.replace()`
- AI: DeepSeek API via OpenAI-compatible client (existing); per-module configurable providers (new — see Section 2)
- Single-file frontend: all JS in `static/app.js`, all CSS in `static/style.css`, one HTML shell at `templates/index.html`

## 1.2 Current File Structure

```
app.py                  — entire backend
static/app.js           — entire frontend
static/style.css        — all styling (dark mode default, light mode toggle)
templates/index.html    — single HTML shell
data/                   — all JSON storage
  projects.json
  inbox.json
  dormant.json
  settings.json
  daily_log.json
  lead_measures.json
  earnings.json
  content_pipeline.json
  posting_log.json
plugins/                — optional Python plugin modules
notes/                  — markdown concept notes
```

## 1.3 Architecture Principles (do not break these)

1. **MIGRATION FIRST.** `migrate()` runs at every startup. It adds new fields with safe defaults, renames keys, and purges stale data. Never require manual JSON editing.
2. **HARD CAPS EVERYWHERE.** Caps enforced at frontend (toast pre-check) and backend (409 response). All caps are stored in `settings.json` under `constants` and read via `get_constants()`.
3. **ENERGY ZONES over priority ranks.** Projects belong to Morning Block, Paid Work, or Evening Block. P1–P4 is a sequence within the zone, not absolute priority.
4. **BRUTAL INBOX.** Items not triaged within 7 days are permanently deleted. No recovery.
5. **SINGLE-FILE FRONTEND.** No build step. State is one plain object. Every action updates state and calls `renderAll()`. API calls use existing GET/POST/PUT/DEL fetch helpers.
6. **PLUGINS.** `/plugins` holds optional Python modules with `manifest` + `execute()`.

## 1.4 Existing Modules (do not remove or break)

| Module | Storage File | Notes |
|--------|-------------|-------|
| Project Manager | `projects.json` | Core module. 3-step capture wizard, edit modal, energy zones, WBS phases |
| Inbox / Dormant | `inbox.json`, `dormant.json` | 7-day hard expiry on inbox; 25-item dormant cap |
| Publishing Central | `content_pipeline.json` | Chapter pipeline across 4 platforms |
| Earnings | `earnings.json` | Manual income log, monthly bar chart |
| Lead Measures | `lead_measures.json` | Monthly outreach counters |
| Posting Tracker | `posting_log.json` | Daily per-platform checkbox + streak |
| Content Pipeline sidebar | `content_pipeline.json` | Condensed sidebar view of Publishing Central |
| Notes | `/notes/*.md` | Free-form markdown notes |
| Settings | `settings.json` | All caps, targets, prompts, WBS templates |

## 1.5 Existing Stubs to Activate

Two stubs already exist in the UI and must be wired up as part of this build:

- **"Start a LivingWriter record?"** — fires after capturing a Creative Development project. Must open the LivingWriter tab and pre-populate a new story record from the project data.
- **"Add to the CRM?"** — fires after capturing a Sales & Funding project. Must open the Promotion Machine tab and pre-populate a new contact/lead from the project data.

## 1.6 Navigation Restructure (Hub Model)

The existing tab bar must be reorganised into a **dashboard-of-dashboards** hub. The user has specified a full restructure — not just adding tabs alongside existing ones.

**New top-level navigation structure:**

```
[ HUB ]  [ TO-DO ]  [ LIVING WRITER ]  [ PUBLISHING CENTRAL ]  [ PROMOTION MACHINE ]  [ SETTINGS ]
```

- **HUB** — new landing view (see Section 2.1). Replaces the current default view.
- **TO-DO** — consolidates the existing Project Manager + Inbox + Dormant + Lead Measures + Posting Tracker + Earnings into one tab. These modules are unchanged functionally; only their navigation entry point changes.
- **LIVING WRITER** — new module (see Section 2.2).
- **PUBLISHING CENTRAL** — existing module, promoted to top-level tab. Unchanged functionally.
- **PROMOTION MACHINE** — new module (see Section 2.3).
- **SETTINGS** — existing module, unchanged functionally.

**Migration impact:** No data changes required for the restructure. Only `index.html` (tab markup) and the `renderAll()` / tab-switching logic in `app.js` are affected.

---

# SECTION 2 — MODULES TO BUILD

---

## 2.1 MODULE: HUB (Dashboard of Dashboards)

### Purpose
Give the user a single-glance view of health and progress across all dashboards, with one-click entry into each. Replaces the current default landing view.

### Data Model
No new JSON file. The Hub reads from existing files and the new module files. It is a read-only aggregation view — it writes nothing.

### Backend Routes

```
GET /api/hub/summary
```
**Response:**
```json
{
  "todo": {
    "active_projects": 4,
    "inbox_count": 3,
    "overdue_projects": 1
  },
  "living_writer": {
    "stories_in_pipeline": 2,
    "furthest_stage": 5,
    "draft_complete_count": 0
  },
  "publishing_central": {
    "chapters_live": 12,
    "chapters_pending": 3
  },
  "promotion_machine": {
    "contacts_count": 47,
    "open_leads": 12,
    "messages_queued": 3
  }
}
```
**Error cases:** 200 always — if a sub-module's file does not yet exist, return 0 for all its fields. Never 500 on missing files.

### Frontend
- Default view when the app loads.
- Four dashboard cards arranged in a 2×2 grid (or horizontal row on wide screens).
- Each card shows: dashboard name, 2–3 key stats pulled from `/api/hub/summary`, and a prominent **Open** button that switches to that tab.
- Cards are read-only. No editing from the Hub.
- Refreshes summary on every tab switch back to Hub (call `GET /api/hub/summary` on Hub tab activation).

### Migration
No migration step required. `/api/hub/summary` handles missing files gracefully.

### Cap/Limit Rules
None.

### Edge Cases
- If `living_writer.json` does not yet exist, Living Writer card shows all zeros. No error.
- If `promotion_machine/` files do not yet exist, Promotion Machine card shows all zeros. No error.

---

## 2.2 MODULE: LIVING WRITER

### Purpose
A 7-stage creative development pipeline that takes a story from raw concept to a fully internalized treatment the writer can draft from without consulting reference material. It is a pipeline manager, not a writing app. Drafting happens in external tools.

**Governing principle:** Every stage exists to move knowledge off the page and into the writer's body. By Stage 7, the writer does not open the app — they write from memory.

### Data Model

**Storage file:** `data/living_writer.json`

**Top-level structure:**
```json
{
  "stories": []
}
```

**Story object:**
```json
{
  "id": "uuid-string",
  "title": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "current_stage": 1,
  "stage_completion": {
    "1": false,
    "2": false,
    "3": false,
    "4": false,
    "5": false,
    "6": false,
    "7": false
  },
  "draft_complete": false,
  "draft_complete_at": null,
  "stage1": {
    "concept_note": "",
    "devonthink_nudge_shown": false
  },
  "stage2": {
    "characters": [],
    "thematic_values": "",
    "historical_catastrophe": null,
    "fragments": [],
    "world_rules": null,
    "leviathan_answers": {},
    "story_genome": "",
    "world_of_story_doc": ""
  },
  "stage3": {
    "arc_brainstorms": [],
    "selected_arc_index": null,
    "four_episode_loglines": [],
    "tsv_output": ""
  },
  "stage4": {
    "treesheets_files": []
  },
  "stage5": {
    "treatment_scenes": [],
    "descriptionary": []
  },
  "stage6": {
    "narrative_summary": "",
    "anki_deck_exported": false,
    "reconstruction_sessions": []
  },
  "stage7": {
    "export_targets": [],
    "session_notes": ""
  }
}
```

**Character object (inside `stage2.characters`):**
```json
{
  "id": "uuid-string",
  "character_in_one_line": "",
  "wound": "",
  "lie": "",
  "crucible": "",
  "terrain": "",
  "transformation": "",
  "what_they_leave_behind": ""
}
```

**Fragment object (inside `stage2.fragments`):**
```json
{
  "id": "uuid-string",
  "occasion_type": "string (one of 7 defined occasions)",
  "content": ""
}
```

**Treatment scene object (inside `stage5.treatment_scenes`):**
```json
{
  "id": "uuid-string",
  "order": 0,
  "slug_line": "",
  "crux": "",
  "scene_description": ""
}
```

**Descriptionary entry (inside `stage5.descriptionary`):**
```json
{
  "id": "uuid-string",
  "header": "",
  "body": ""
}
```

**Leviathan answer object (inside `stage2.leviathan_answers`):**
Keys are question IDs `"q1"` through `"q52"`. Values are strings (the writer's answer).

**TreeSheets file object (inside `stage4.treesheets_files`):**
```json
{
  "id": "uuid-string",
  "label": "",
  "filepath": ""
}
```

**Arc brainstorm object (inside `stage3.arc_brainstorms`):**
```json
{
  "id": "uuid-string",
  "character_id": "uuid-string",
  "primary_arc_type": "Positive | Negative | Flat",
  "primary_arc_rationale": "",
  "secondary_arc_type": "",
  "secondary_arc_explanation": "",
  "lie": "",
  "truth": "",
  "core_wound": "",
  "arc_summary": "",
  "editorial_recommendation": ""
}
```

**Four-episode logline object (inside `stage3.four_episode_loglines`):**
```json
{
  "act": "Act 1 | Act 2 Part 1 | Act 2 Part 2 | Act 3",
  "logline": ""
}
```

### Backend Routes

All routes prefixed `/api/lw/`.

```
GET    /api/lw/stories                          — list all stories
POST   /api/lw/stories                          — create story
  Body: { "title": "string" }
  Returns: full story object
  Errors: 400 if title missing or empty

GET    /api/lw/stories/<id>                     — get single story
  Errors: 404 if not found

PUT    /api/lw/stories/<id>                     — update any field(s) of story
  Body: partial story object (any fields)
  Returns: updated story object
  Errors: 404 if not found; 400 if body is not a dict

DELETE /api/lw/stories/<id>                     — delete story
  Errors: 404 if not found

POST   /api/lw/stories/<id>/advance             — advance current_stage by 1
  Validates: current_stage must be < 7
  Returns: updated story object
  Errors: 404; 409 if already at stage 7

POST   /api/lw/stories/<id>/complete            — mark Stage 7 draft-complete
  Sets: draft_complete=true, draft_complete_at=now
  Also: sends draft-complete signal to Indaba (see Section 3.1)
  Returns: updated story object
  Errors: 404; 409 if current_stage < 7

GET    /api/lw/stories/<id>/cruxes              — extract crux-only list from treatment
  Returns: [ { "order": int, "slug_line": str, "crux": str }, ... ]
  Sorted by scene order ascending
  Errors: 404

POST   /api/lw/stories/<id>/stage2/derive_thematic_values
  Reads all character Crucible fields for this story
  Calls AI to derive 2–3 dominant tensions
  Returns: { "thematic_values": "string (max 300 words)" }
  Uses: AI provider configured for lw_thematic_values in settings
  Errors: 404; 502 if AI call fails

POST   /api/lw/stories/<id>/stage3/arc_brainstorm
  Body: { "character_id": "uuid-string" }
  Calls AI with character arc data + story world context
  Generates 3 distinct arc possibilities
  Returns: arc_brainstorm object (saved to story)
  Errors: 404; 400 if character_id missing; 502 if AI fails

POST   /api/lw/stories/<id>/stage3/generate_loglines
  Body: { "brainstorm_id": "uuid-string" }
  Calls AI with selected arc brainstorm
  Generates 4 loglines (exactly 25 words each, present tense, third person)
  Saves to story.stage3.four_episode_loglines
  Also generates tsv_output string (tab-separated, Act [TAB] Logline)
  Returns: { "loglines": [...], "tsv_output": "string" }
  Errors: 404; 400 if brainstorm_id missing; 502 if AI fails

POST   /api/lw/stories/<id>/stage6/export_anki
  Reads treatment_scenes from stage5
  Generates Anki flashcard deck (concrete action beats only)
  Exports as .apkg file to /data/exports/<story_id>_anki.apkg
  Returns: { "download_url": "/data/exports/<story_id>_anki.apkg" }
  Errors: 404; 500 if export fails

POST   /api/lw/stories/<id>/stage7/export
  Body: { "target": "final_draft | scrivener | novelwriter | ulysses | freewrite", "format": "treatment | cruxes" }
  Exports treatment or crux-only list as appropriate file format
  Returns: { "download_url": "/data/exports/<story_id>_<target>.<ext>" }
  Errors: 404; 400 if target or format invalid
```

### Stage 2 — World Engine: The Leviathan

The Leviathan is a 52-question worksheet. Questions are stored as static data in `app.py` (a Python list of dicts), not in JSON. Each question has:
```python
{
  "id": "q1",          # q1–q52
  "part": 1,           # 1–10 (the 10 parts)
  "part_label": "str",
  "question": "str",
  "genome_refs": ["characters", "world_rules"]  # which Story Genome sections to surface
}
```

The Leviathan route:
```
GET /api/lw/leviathan/questions     — return all 52 questions with their part labels
```
No backend needed for individual answer save — answers are saved via `PUT /api/lw/stories/<id>` updating `stage2.leviathan_answers`.

AI assistance per question:
```
POST /api/lw/stories/<id>/stage2/leviathan_assist
  Body: { "question_id": "q1" }
  Calls AI with: question text + all current Story Genome sections + previous Leviathan answers
  Returns: { "suggestion": "string", "contradictions": ["string"] }
  Errors: 404; 400 if question_id not in q1–q52; 502 if AI fails
```

### Frontend

**Tab:** LIVING WRITER (top-level nav)

**Default view: Pipeline Dashboard**
- One horizontal progress bar per story.
- Bar fill = `(current_stage - 1) / 6 * 100%` (Stage 1 = ~0%, Stage 7 = 100%).
- Show: story title, current stage name, last updated date.
- Click story → open Story Detail view.
- Button: **+ New Story** → modal asking for title → POST `/api/lw/stories`.

**Story Detail view:**
- Left sidebar: stage map (Stages 1–7 listed vertically). Active stage highlighted. Completed stages marked with checkmark. Click any stage to jump to it.
- Main panel: content for the active stage.
- Top right: **Mark Stage Complete** button → calls `POST /api/lw/stories/<id>/advance`.
- Stage 7 shows **Mark Draft Complete** instead → calls `POST /api/lw/stories/<id>/complete`.

**Stage 1 panel:**
- Textarea for concept note (auto-saves on blur via `PUT /api/lw/stories/<id>`).
- On first entry to Stage 1 (when `devonthink_nudge_shown` is false): show modal nudge — *"Do you have existing material on this concept in DEVONthink? Notes, research, prior drafts, clippings?"* — with **Got it** button. Sets `devonthink_nudge_shown: true`.

**Stage 2 panel:**
- Five module sections: Character Arc Outlines (compulsory), Thematic Values (auto-derived), Historical Catastrophe (optional), Fragments (compulsory), World's Rules (optional).
- Character Arc Outlines: **+ Add Character** button → inline form with all 7 fields. Each field has a **Show example** toggle showing 2–3 examples. Examples are hidden by default.
- Min 2 characters required before Stage 2 can be marked complete. Max 6. Return 409 if user tries to add a 7th.
- **Derive Thematic Values** button → calls AI derive route → displays result in read-only textarea. Writer can edit before saving.
- Fragments: 5 required occasions listed as prompts. Two optional occasions available via **+ Add optional fragment**. Each fragment is a textarea. Max 80 words enforced client-side (word count shown live).
- Leviathan section: shows all 52 questions grouped by part. Each question shows: question text, relevant Story Genome sections in a collapsible side panel, writer's answer textarea, **AI Assist** button. Questions are not gated — completable in any order.
- **Compile Story Genome** button → auto-assembles all completed module content into `story_genome` field. Calls `PUT /api/lw/stories/<id>` to save.

**Stage 3 panel:**
- Per-character arc brainstorm: select character from dropdown → **Generate Arc Brainstorm** → shows 3 arc options. Writer selects one.
- **Generate Loglines** button → calls logline route → shows 4 loglines in a table (Act | Logline).
- **Copy as TSV** button → copies `tsv_output` to clipboard.
- Antinet nudge (shown when writer has been on Stage 3 for > 5 minutes without generating loglines): *"Stuck on a plot beat or story event? Consult the Antinet."* — dismissible, does not reappear for this story once dismissed.

**Stage 4 panel:**
- List of linked TreeSheets files with labels.
- **+ Link File** → modal asking for label and filepath. Saves to `stage4.treesheets_files`.
- Each entry has an **Open** button → calls `os.startfile()` (Windows) or `subprocess.call(['open', filepath])` (Mac) via:
  ```
  POST /api/lw/stories/<id>/stage4/open_file
  Body: { "filepath": "string" }
  Returns: { "ok": true }
  Errors: 404 if story not found; 400 if filepath empty; 500 if OS open fails
  ```

**Stage 5 panel:**
- Treatment: list of scenes. **+ Add Scene** → inline form (slug line, crux, scene description). Scenes are reorderable via drag-and-drop (update `order` fields on drop, save via PUT).
- **Crux View** toggle → hides scene_description, shows slug_line + crux only. This is the writer's drafting reference view.
- Descriptionary: list of entries. **+ Add Entry** → inline form (header, body). Word count shown live; 50–100 word range enforced with warning (not a hard block).

**Stage 6 panel:**
- Narrative Summary textarea. Auto-saves on blur.
- **Export Anki Deck** button → calls export route → provides download link.
- Reconstruction sessions log: **+ Log Session** → textarea for notes, saved to `reconstruction_sessions` array with timestamp.

**Stage 7 panel:**
- **Export to [target]** buttons for each supported target (Final Draft, Scrivener, novelWriter, Ulysses, FreeWrite).
- Format selector: Treatment or Cruxes Only.
- Session notes textarea.
- **Mark Draft Complete** button (prominent, accent color) → calls complete route → shows confirmation toast → Hub summary updates on next load.

### Migration

On first boot with `living_writer.json` absent:
```python
if not os.path.exists(LIVING_WRITER_FILE):
    write_json(LIVING_WRITER_FILE, {"stories": []})
```
On subsequent boots: iterate all stories and add any missing fields with defaults listed in the data model above. Do not overwrite existing values.

### Cap/Limit Rules

| Limit | Value | Configurable |
|-------|-------|-------------|
| Max stories in pipeline | 20 | Yes — `settings.json` → `constants.lw_max_stories` |
| Max characters per story | 6 | No |
| Min characters to complete Stage 2 | 2 | No |
| Max fragments (including optional) | 7 | No |
| Descriptionary entry word range | 50–100 | Warning only, not hard block |
| Logline word count | exactly 25 | Enforced by AI prompt; display word count in UI |

### Edge Cases

- **Stage advance without completing required fields:** If user clicks Mark Stage Complete on Stage 2 without minimum 2 characters, return 409 with message `"Stage 2 requires at least 2 Character Arc Outlines before advancing."` Same pattern for other stage-specific requirements.
- **AI failure on any LW route:** Return 502 with `{ "error": "AI provider unavailable", "detail": "..." }`. Frontend shows toast error. Never lose the writer's existing data.
- **Concurrent edits:** Not applicable (single user). Last write wins.
- **File open failure (Stage 4):** If `os.startfile()` or `open` call fails (file not found, OS error), return 500 with `{ "error": "Could not open file. Check that the path is correct and the file exists." }`.
- **Anki export with no scenes:** If `stage5.treatment_scenes` is empty, return 400 with `{ "error": "No treatment scenes found. Complete Stage 5 before exporting an Anki deck." }`.
- **TSV copy on empty loglines:** Disable Copy as TSV button if `tsv_output` is empty.

---

## 2.3 MODULE: PROMOTION MACHINE

The Promotion Machine has three sub-systems: **Content Creator** (Message Maker, Book Serializer, WhatsApp Post Maker), **Content Sender** (queue-based WhatsApp Web automation via Claude Cowork), and **Contacts CRM** (contact management + sales pipeline).

### 2.3.1 Storage Files

```
data/promo_contacts.json      — contact records
data/promo_leads.json         — leads (contacts in sales pipelines)
data/promo_messages.json      — message queue (scheduled + sent)
data/promo_proverbs.json      — African proverbs library
data/promo_books.json         — ingested book/chapter content for serializer
data/promo_settings.json      — per-module AI provider config + CTA links
```

### 2.3.2 Data Models

**Contact object (`promo_contacts.json → contacts[]`):**
```json
{
  "id": "uuid-string",
  "name": "string",
  "phone": "string (E.164 format, e.g. +27821234567)",
  "email": "",
  "tags": [],
  "source": "manual | csv | whatsapp_web",
  "notes": "",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

**Lead object (`promo_leads.json → leads[]`):**
```json
{
  "id": "uuid-string",
  "contact_id": "uuid-string",
  "product": "string (event name, campaign name, platform name — free text)",
  "product_type": "event | campaign | membership | other",
  "stage": "lead | qualified | proposal | negotiation | won | lost",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "notes": "",
  "communication_log": []
}
```

**Communication log entry (inside `lead.communication_log`):**
```json
{
  "id": "uuid-string",
  "timestamp": "ISO8601",
  "direction": "outbound | inbound",
  "channel": "whatsapp",
  "message": "string",
  "message_id": "uuid or null (links to promo_messages.json entry if outbound)"
}
```

**Message queue entry (`promo_messages.json → messages[]`):**
```json
{
  "id": "uuid-string",
  "recipient_phone": "string",
  "recipient_name": "string",
  "content": "string",
  "status": "queued | sent | failed",
  "scheduled_at": "ISO8601 or null (null = send immediately on next sender run)",
  "sent_at": "ISO8601 or null",
  "created_at": "ISO8601",
  "source": "message_maker | book_serializer | wa_post_maker | crm",
  "lead_id": "uuid or null",
  "bulk_batch_id": "uuid or null"
}
```

**Proverb object (`promo_proverbs.json → proverbs[]`):**
```json
{
  "id": "uuid-string",
  "text": "string",
  "origin": "string (tribe/region, optional)",
  "used": false,
  "used_at": "ISO8601 or null",
  "generated_meaning": "",
  "generated_image_prompt": "",
  "generated_image_url": "",
  "post_content": ""
}
```

**Book/chapter object (`promo_books.json → books[]`):**
```json
{
  "id": "uuid-string",
  "title": "string",
  "author": "string",
  "patreon_url": "string",
  "website_url": "string",
  "chunks": [],
  "created_at": "ISO8601"
}
```

**Chunk object (inside `book.chunks`):**
```json
{
  "id": "uuid-string",
  "order": 0,
  "content": "string",
  "word_count": 0,
  "cliffhanger_note": "string (AI-generated note on why this is the break point)",
  "cta": "string",
  "status": "pending | queued | sent"
}
```

**Promo settings (`promo_settings.json`):**
```json
{
  "ai_providers": {
    "message_maker": { "provider": "deepseek", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY" },
    "book_serializer": { "provider": "deepseek", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY" },
    "wa_post_maker": { "provider": "deepseek", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY" },
    "crm_assist": { "provider": "deepseek", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY" },
    "image_gen": { "provider": "", "model": "", "api_key_env": "", "endpoint": "" }
  },
  "cta_links": {
    "patreon_url": "",
    "website_url": ""
  },
  "serializer_defaults": {
    "target_chunk_word_count": 300,
    "max_chunk_word_count": 400
  },
  "wa_channel_branding": {
    "channel_name": "",
    "channel_description": "",
    "cta_emoji": "👇",
    "cta_text": "React with an emoji if this resonated with you."
  }
}
```

### 2.3.3 Backend Routes — Contacts

```
GET    /api/promo/contacts                    — list all contacts
POST   /api/promo/contacts                    — create one contact
  Body: { "name": "string (required)", "phone": "string (required)", "email": "", "tags": [], "source": "manual", "notes": "" }
  Validates: name non-empty; phone non-empty; phone matches E.164 pattern ^\+\d{7,15}$
  Errors: 400 if name missing; 400 if phone missing or invalid format; 409 if phone already exists

POST   /api/promo/contacts/import_csv
  Body: multipart/form-data, field "file" is a .csv file
  CSV must have columns: name, phone (required); email, tags (optional)
  Skips rows with missing name or invalid phone (logs skipped count)
  Skips duplicate phones (logs skipped count)
  Returns: { "imported": int, "skipped_invalid": int, "skipped_duplicate": int }
  Errors: 400 if no file; 400 if file is not .csv

GET    /api/promo/contacts/<id>               — get single contact with all leads
  Returns: contact object + leads[] array filtered to this contact_id
  Errors: 404

PUT    /api/promo/contacts/<id>               — update contact fields
  Errors: 404; 400 if phone format invalid

DELETE /api/promo/contacts/<id>               — delete contact
  Also deletes all leads where contact_id = id
  Also removes contact from any queued messages (set recipient_name to "[Deleted]", do not delete message)
  Errors: 404

POST   /api/promo/contacts/<id>/tags
  Body: { "tags": ["string", ...] }
  Replaces tag list entirely
  Errors: 404; 400 if tags is not an array

GET    /api/promo/contacts/by_tag/<tag>       — list contacts with a specific tag
  Returns: contacts[] filtered by tag
```

### 2.3.4 Backend Routes — Leads

```
GET    /api/promo/leads                       — list all leads (optionally filter by stage or contact)
  Query params: stage=lead|qualified|..., contact_id=uuid

POST   /api/promo/leads
  Body: { "contact_id": "uuid (required)", "product": "string (required)", "product_type": "event|campaign|membership|other", "notes": "" }
  Errors: 400 if contact_id or product missing; 404 if contact_id not found in contacts

GET    /api/promo/leads/<id>                  — get lead with full communication log
  Errors: 404

PUT    /api/promo/leads/<id>
  Body: partial lead fields (stage, notes, product, product_type)
  Errors: 404; 400 if stage is not one of the 6 valid values

DELETE /api/promo/leads/<id>
  Errors: 404

POST   /api/promo/leads/<id>/log_communication
  Body: { "direction": "outbound|inbound", "message": "string", "message_id": "uuid or null" }
  Appends to lead.communication_log
  Errors: 404; 400 if direction or message missing

POST   /api/promo/leads/<id>/ai_suggest_next_message
  Reads lead's communication_log (last 5 entries) + current stage + product
  Calls AI (crm_assist provider) to suggest next message to advance lead
  Returns: { "suggested_message": "string" }
  Errors: 404; 502 if AI fails
```

### 2.3.5 Backend Routes — Message Maker

```
POST   /api/promo/message_maker/generate
  Body: {
    "purpose": "string (what is this message promoting?)",
    "event_name": "string",
    "event_date": "string",
    "target_audience": "string",
    "tone_notes": "string",
    "recipient_name": "string (optional, for personalisation)"
  }
  Calls AI (message_maker provider) with built-in system prompt (see below)
  Returns: { "message": "string" }
  Errors: 400 if purpose missing; 502 if AI fails
```

**Message Maker system prompt (stored in `app.py` as a constant):**
```
You are a WhatsApp message writer for a South African author and content creator.
Write a single WhatsApp message that achieves the following purpose: {purpose}.
Tone: warm, direct, personal. Never corporate. Never salesy.
Length: 50–120 words maximum.
Structure: 1 opening hook sentence. 1–2 sentences of context. 1 clear call to action.
No emojis unless specified. No bullet points. Plain conversational prose.
End with a single specific action the recipient should take.
Return only the message text. No preamble. No explanation.
```

### 2.3.6 Backend Routes — Book Serializer

```
GET    /api/promo/books                       — list all books

POST   /api/promo/books
  Body: { "title": "string", "author": "string", "patreon_url": "", "website_url": "" }
  Errors: 400 if title missing

PUT    /api/promo/books/<id>
  Errors: 404

DELETE /api/promo/books/<id>
  Errors: 404

POST   /api/promo/books/<id>/ingest
  Body: multipart/form-data OR JSON
  If multipart: field "file" is .txt or .docx file; field "input_type" = "file"
  If JSON: { "text": "string", "input_type": "paste" }
  Replaces all existing chunks for this book
  Calls AI (book_serializer provider) to break text into chunks:
    - Target chunk word count from promo_settings.serializer_defaults.target_chunk_word_count (default 300)
    - Max chunk word count from promo_settings.serializer_defaults.max_chunk_word_count (default 400)
    - Each chunk ends at an emotional cliffhanger or point of suspense
    - Each chunk ends with a CTA linking to patreon_url or website_url (whichever is set)
  Returns: { "chunks": [...], "total_chunks": int }
  Errors: 404; 400 if neither text nor file provided; 400 if file is not .txt or .docx; 502 if AI fails

GET    /api/promo/books/<id>/chunks           — list all chunks for a book

POST   /api/promo/books/<id>/chunks/<chunk_id>/queue
  Sets chunk.status = "queued"
  Creates a message queue entry in promo_messages.json
  Body: { "scheduled_at": "ISO8601 or null" }
  Returns: { "message_id": "uuid" }
  Errors: 404; 409 if chunk already queued or sent
```

**Book Serializer AI system prompt (stored in `app.py`):**
```
You are serializing a novel chapter into WhatsApp-ready segments for a South African author's WhatsApp channel.

Rules:
- Target length per segment: {target_words} words. Hard maximum: {max_words} words.
- Cut each segment at the most emotionally charged moment — a cliffhanger, unanswered question, or moment of peak suspense. Never cut mid-sentence.
- Each segment must end with this call to action (append exactly as written): {cta}
- Do not add chapter headings, segment numbers, or any metadata.
- Return a JSON array. Each element: { "content": "segment text including CTA", "cliffhanger_note": "one sentence explaining why this is the break point" }
- Return only the JSON array. No preamble.
```

### 2.3.7 Backend Routes — WhatsApp Post Maker

```
GET    /api/promo/proverbs                    — list all proverbs
  Query param: used=true|false (optional filter)

POST   /api/promo/proverbs                    — add a single proverb manually
  Body: { "text": "string", "origin": "" }
  Errors: 400 if text missing

POST   /api/promo/proverbs/import_bulk
  Body: { "proverbs": [ { "text": "string", "origin": "" }, ... ] }
  Returns: { "imported": int }
  Errors: 400 if proverbs is not a non-empty array

POST   /api/promo/wa_post/generate
  Picks the oldest unused proverb (lowest index in array where used=false)
  Calls AI (wa_post_maker provider) to:
    1. Generate meaning of the proverb (max 40 words)
    2. Generate image prompt for the proverb (max 60 words, visual, no text in image)
  Calls image generation API (image_gen provider) with image prompt
  Saves meaning, image_prompt, image_url to the proverb record
  Assembles final post_content: "[image_url]\n\n{proverb text}\n\n{meaning}\n\n{cta_text}"
  Marks proverb as used (used=true, used_at=now)
  Returns: { "proverb_id": "uuid", "post_content": "string", "image_url": "string" }
  Errors: 409 if no unused proverbs remain; 502 if AI or image gen fails

  [DECISION NEEDED: The image generation provider and endpoint are not yet specified. The image_gen block in promo_settings.json has an "endpoint" field for a custom API URL. The build must implement a generic HTTP POST to that endpoint with { "prompt": "string" } and expect { "url": "string" } in response. The user will configure the actual provider (e.g. Kimi Moonshot) via Settings. Until the image_gen provider is configured, the generate route must return a 503 with { "error": "Image generation provider not configured. Set it in Promotion Machine Settings." } rather than proceeding without an image.]

POST   /api/promo/wa_post/<proverb_id>/queue
  Creates a message queue entry from the proverb's post_content
  Body: { "scheduled_at": "ISO8601 or null", "recipient_phone": "string (channel phone or specific contact)" }
  Errors: 404; 409 if proverb not yet generated (post_content empty)
```

### 2.3.8 Backend Routes — Message Queue & Sender

```
GET    /api/promo/messages                    — list all messages
  Query params: status=queued|sent|failed (optional); limit=int (default 50)

GET    /api/promo/messages/<id>
  Errors: 404

DELETE /api/promo/messages/<id>
  Only deletable if status=queued
  Errors: 404; 409 if status=sent or failed

POST   /api/promo/messages/<id>/reschedule
  Body: { "scheduled_at": "ISO8601" }
  Only reschedulable if status=queued or failed
  Errors: 404; 409 if status=sent

POST   /api/promo/sender/process_queue
  Scans all messages where status=queued AND (scheduled_at is null OR scheduled_at <= now)
  For each qualifying message: triggers Claude Cowork automation (see below)
  Returns: { "processed": int, "failed": int, "details": [...] }

POST   /api/promo/sender/send_now
  Body: { "message_id": "uuid" }
  Sends a single specific queued message immediately regardless of scheduled_at
  Errors: 404; 409 if not status=queued
```

**WhatsApp Web Automation via Claude Cowork:**

The sender uses Claude Cowork (desktop automation agent) to open WhatsApp Web and send messages. The Flask backend triggers Cowork by writing a job file and waiting for a result file. This is the integration contract:

1. Backend writes `/data/cowork_jobs/<message_id>.json`:
   ```json
   {
     "message_id": "uuid",
     "recipient_phone": "+27821234567",
     "recipient_name": "Jane",
     "content": "message text",
     "created_at": "ISO8601"
   }
   ```
2. Cowork picks up the job file, opens WhatsApp Web, navigates to the contact by phone number, pastes the message content, sends it.
3. Cowork writes `/data/cowork_results/<message_id>.json`:
   ```json
   {
     "message_id": "uuid",
     "status": "sent | failed",
     "sent_at": "ISO8601 or null",
     "error": "string or null"
   }
   ```
4. Backend polls for the result file (max 60 seconds, 2-second intervals). On result:
   - `sent`: set `message.status = "sent"`, `message.sent_at = sent_at`. Log to lead communication log if `lead_id` is set.
   - `failed`: set `message.status = "failed"`. Show error in sender UI.
   - Timeout: set `message.status = "failed"` with `error = "Cowork timeout"`.

[DECISION NEEDED: Cowork job pickup mechanism is not specified. Does Cowork watch the `/data/cowork_jobs/` directory for new files, or does Indaba call a Cowork API endpoint? This must be resolved before implementing the sender. The brief assumes file-based handoff as above — confirm or replace this mechanism.]

**On app startup:** `migrate()` calls `process_overdue_queue()` — a helper that scans for messages where `status=queued` AND `scheduled_at <= now`. These are messages that should have been sent while the system was off. It does NOT send them automatically on startup; it flags them as `status="overdue"` (add this status value) and surfaces them in the sender UI with a banner: *"X messages are overdue. Send now?"* The user confirms before processing.

### 2.3.9 Backend Routes — Bulk Messaging

```
POST   /api/promo/messages/bulk
  Body: {
    "tag": "string (filter contacts by this tag)",
    "content": "string (message body, may include {name} placeholder)",
    "scheduled_at": "ISO8601 or null",
    "source": "message_maker | manual"
  }
  Finds all contacts with the given tag
  Creates one message queue entry per contact (substituting {name} with contact.name if present)
  Assigns a shared bulk_batch_id (new uuid) to all entries
  Returns: { "batch_id": "uuid", "message_count": int, "contacts": [{ "name": str, "phone": str }] }
  Errors: 400 if tag or content missing; 404 if no contacts found with that tag

GET    /api/promo/messages/bulk/<batch_id>    — get all messages in a batch
```

### 2.3.10 Frontend — Promotion Machine

**Tab:** PROMOTION MACHINE (top-level nav)

**Sub-tabs within the Promotion Machine tab:**
```
[ CONTACTS ]  [ LEADS ]  [ MESSAGE MAKER ]  [ BOOK SERIALIZER ]  [ WA POST MAKER ]  [ SENDER ]  [ SETTINGS ]
```

**CONTACTS sub-tab:**
- Table of all contacts: Name, Phone, Tags, Open Leads count, Actions.
- **+ Add Contact** button → modal (name required, phone required, email optional, tags optional).
- **Import CSV** button → file picker → calls import_csv route → shows result toast.
- [DECISION NEEDED: WhatsApp Web contact import is described as "go on WhatsApp Web, select contacts, they are added to the database." This requires either browser extension access or Cowork automation. The mechanism is not technically specified. Flag this as a future feature and implement manual + CSV import only for v1.]
- Click contact row → Contact Detail panel (slide-in or modal):
  - Contact fields (editable inline).
  - Tags (editable chip input).
  - **All Leads** section: list all leads for this contact across all products, showing stage for each.
  - **All Communications** section: consolidated chronological log of all communication entries across all this contact's leads.
  - **+ New Lead** button.

**LEADS sub-tab:**
- Kanban board: 6 columns (lead → qualified → proposal → negotiation → won → lost).
- Each card: contact name, product name, product type badge, last communication date.
- Click card → Lead Detail panel:
  - Product, product type, stage selector (dropdown), notes.
  - Communication log (chronological, showing direction, message, timestamp).
  - **Log Inbound Message** → textarea → saves to communication log with direction=inbound.
  - **Compose Outbound Message** → textarea → two buttons: **Send Now** (creates queued message with scheduled_at=null) and **Schedule** (date/time picker → creates queued message with scheduled_at set). Both call `/api/promo/leads/<id>/log_communication` and create a message queue entry.
  - **AI: Suggest Next Message** button → calls ai_suggest route → populates Compose Outbound textarea.

**MESSAGE MAKER sub-tab:**
- Form: Purpose (required), Event Name, Event Date, Target Audience, Tone Notes, Recipient Name.
- **Generate Message** button → shows generated message in a textarea (editable).
- **Send to Sender** button → creates a message queue entry (phone required — show phone input field).
- **Send to Bulk** button → tag picker → creates a bulk batch.

**BOOK SERIALIZER sub-tab:**
- Left panel: list of books. **+ New Book** button.
- Right panel (selected book):
  - Book fields (title, author, Patreon URL, Website URL).
  - **Ingest Content** section: tab toggle between **Paste Text** (large textarea) and **Upload File** (.txt or .docx picker).
  - **Serializer settings:** Target word count, Max word count (editable, saves to promo_settings).
  - **Serialize** button → calls ingest route → shows chunks below.
  - Chunks list: each chunk shows content preview, word count, cliffhanger note, status badge.
  - Per-chunk: **Queue** button → schedule picker → calls queue route.
  - **Queue All Pending** button → queues all chunks with status=pending in sequence with user-specified start date and interval (e.g., one chunk per day).

  [DECISION NEEDED: "Queue All Pending" interval scheduling is not specified. Suggest: modal asks for start date/time and interval in days. Chunk 1 = start, chunk 2 = start + interval, etc. Confirm this is the desired behaviour.]

**WA POST MAKER sub-tab:**
- **Generate Next Post** button → calls generate route → shows:
  - Proverb text
  - Generated meaning
  - Generated image (rendered as `<img>` tag if image_url is set)
  - Assembled post_content in a read-only textarea
- **Queue Post** button → phone/channel input + schedule picker → calls queue route.
- **Proverbs Library** section:
  - Table of all proverbs: text, origin, used status.
  - **+ Add Proverb** button.
  - **Import Bulk** button → paste JSON array or upload .json file.

**SENDER sub-tab:**
- If overdue messages exist: yellow banner with count + **Process Overdue** button.
- Message queue table: columns — Recipient, Content preview, Status, Scheduled At, Source, Actions.
- Filter by status (queued / sent / failed / overdue).
- Per-row actions: **Send Now** (queued only), **Reschedule** (queued/failed only), **Delete** (queued only).
- **Process Queue** button → calls process_queue route → shows progress and result.

**SETTINGS sub-tab (within Promotion Machine):**
- AI provider configuration per module: for each of message_maker, book_serializer, wa_post_maker, crm_assist, image_gen — show provider name input, model input, API key env var input, and (for image_gen) endpoint URL input.
- CTA Links: Patreon URL, Website URL.
- Serializer defaults: target word count, max word count.
- WA Channel Branding: channel name, description, CTA emoji, CTA text.
- **Save Settings** button → PUT `/api/promo/settings`.

Additional routes for settings:
```
GET  /api/promo/settings     — return promo_settings.json
PUT  /api/promo/settings     — update promo_settings.json (full replace)
  Errors: 400 if body is not a dict
```

### Migration — Promotion Machine

On first boot:
```python
for f in [PROMO_CONTACTS_FILE, PROMO_LEADS_FILE, PROMO_MESSAGES_FILE,
          PROMO_PROVERBS_FILE, PROMO_BOOKS_FILE]:
    if not os.path.exists(f):
        write_json(f, {"contacts": []} if "contacts" in f else
                      {"leads": []} if "leads" in f else
                      {"messages": []} if "messages" in f else
                      {"proverbs": []} if "proverbs" in f else
                      {"books": []})

if not os.path.exists(PROMO_SETTINGS_FILE):
    write_json(PROMO_SETTINGS_FILE, DEFAULT_PROMO_SETTINGS)  # use the default object from data model above
```

Also create directories:
```python
os.makedirs('data/cowork_jobs', exist_ok=True)
os.makedirs('data/cowork_results', exist_ok=True)
os.makedirs('data/exports', exist_ok=True)
```

### Cap/Limit Rules — Promotion Machine

| Limit | Value | Configurable |
|-------|-------|-------------|
| Max contacts | 10,000 | No |
| Max open leads per contact | 10 | Yes — `promo_settings.max_leads_per_contact` (add this field) |
| Max messages in queue | 500 | No |
| Max proverbs in library | 5,000 | No |
| Max books | 50 | No |
| Max chunks per book | 500 | No |

### Edge Cases — Promotion Machine

- **Duplicate phone on contact import (CSV):** Skip silently, count in `skipped_duplicate`.
- **Invalid E.164 phone on manual add:** Return 400 with `{ "error": "Phone must be in E.164 format, e.g. +27821234567" }`.
- **Generate WA post with no unused proverbs:** Return 409 with `{ "error": "All proverbs have been used. Import more proverbs to continue." }`.
- **Image gen provider not configured:** Return 503 with specific message (see route spec above).
- **Cowork timeout:** Set message to failed, surface in Sender UI with error detail.
- **Delete contact with active leads:** Delete the leads too (cascade). Do not block deletion.
- **Serializer on empty text input:** Return 400 with `{ "error": "Input text is empty." }`.
- **Queue a chunk that is already queued:** Return 409 with `{ "error": "This chunk is already in the send queue." }`.
- **AI suggest next message with empty communication log:** Send only lead stage + product context to AI, without communication history. Do not error.

---

# SECTION 3 — CHANGES TO EXISTING MODULES

## 3.1 Project Manager → Living Writer (draft-complete signal)

When `POST /api/lw/stories/<id>/complete` is called:
1. Find the Indaba project in `projects.json` where `name` matches `story.title` AND `pipeline = "Creative Development"`.
2. If found: set `project.phase = "Draft Complete"` and add a session note: `"LivingWriter: draft-complete signal received at {ISO8601}"`.
3. If no matching project found: log a warning to console but do not error. The signal is best-effort.

[DECISION NEEDED: Should the Living Writer → Indaba signal match on story title to find the project, or should there be an explicit `indaba_project_id` field on the story object? Title matching is fragile if the names diverge. Recommend adding `indaba_project_id: null` to the story data model and populating it when the LivingWriter tab is opened from the "Start a LivingWriter record?" stub flow.]

## 3.2 Project Manager → Promotion Machine (CRM stub activation)

When the user clicks **"Add to the CRM?"** after capturing a Sales & Funding project:
1. Switch to Promotion Machine tab → Contacts sub-tab.
2. Pre-populate the **+ Add Contact** modal with the project name in the "notes" field and a tag matching the project name.
3. Do not auto-create a contact — require user confirmation.

## 3.3 Settings → Promotion Machine AI Providers

The existing Settings module is not modified. AI provider configuration for the Promotion Machine lives in `promo_settings.json` and is managed via the SETTINGS sub-tab within the Promotion Machine tab. Do not merge it into the main `settings.json`.

## 3.4 Hub → All Modules (summary aggregation)

`GET /api/hub/summary` must be added to `app.py` and must read from:
- `projects.json` for the TO-DO card
- `living_writer.json` for the Living Writer card
- `content_pipeline.json` for the Publishing Central card
- `promo_contacts.json` + `promo_leads.json` + `promo_messages.json` for the Promotion Machine card

If any file does not exist, return 0 for its fields. Never 500.

## 3.5 Navigation Restructure

**In `index.html`:** Replace the existing tab bar markup with the new hub navigation structure:
```
HUB | TO-DO | LIVING WRITER | PUBLISHING CENTRAL | PROMOTION MACHINE | SETTINGS
```

**In `app.js`:**
- Add `currentTopTab` to state (default: `"hub"`).
- The TO-DO tab renders the same content as the existing default view: Projects, Inbox, Dormant, Lead Measures, Posting Tracker, Earnings, and the Content Pipeline sidebar. No functional changes to these modules — only their navigation entry point changes.
- `renderAll()` must check `state.currentTopTab` and render the appropriate top-level view.
- All existing sub-tab logic (e.g., within the former Publishing Central view) remains unchanged.

---

# SECTION 4 — TESTING CHECKLIST

## 4.1 Hub

```bash
# After first boot, all files exist
curl http://localhost:5050/api/hub/summary
# Expected: 200, all counts are 0 or reflect existing data

# Delete living_writer.json, restart, call summary
curl http://localhost:5050/api/hub/summary
# Expected: 200, living_writer fields are 0 (no 500)
```

User actions:
- Open app → confirm Hub is the default view.
- Confirm all four dashboard cards render with correct counts.
- Click Open on each card → confirm correct tab loads.

## 4.2 Navigation Restructure

User actions:
- Click each top-level tab → confirm correct content loads.
- TO-DO tab → confirm all existing modules (Projects, Inbox, Lead Measures, etc.) still work identically.
- Confirm dark/light mode toggle still works from all tabs.

## 4.3 Living Writer

```bash
# Create story
curl -X POST http://localhost:5050/api/lw/stories \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Story"}'
# Expected: 201, story object with id

STORY_ID=<id from above>

# Get story
curl http://localhost:5050/api/lw/stories/$STORY_ID
# Expected: 200, story object

# Update Stage 1 concept note
curl -X PUT http://localhost:5050/api/lw/stories/$STORY_ID \
  -H "Content-Type: application/json" \
  -d '{"stage1": {"concept_note": "A story about loss.", "devonthink_nudge_shown": true}}'
# Expected: 200, updated story

# Advance stage
curl -X POST http://localhost:5050/api/lw/stories/$STORY_ID/advance
# Expected: 200, current_stage=2

# Advance to stage 7 (advance 5 more times)
# then attempt to advance again
curl -X POST http://localhost:5050/api/lw/stories/$STORY_ID/advance
# Expected: 409

# Mark draft complete
curl -X POST http://localhost:5050/api/lw/stories/$STORY_ID/complete
# Expected: 200, draft_complete=true

# Get cruxes with no treatment scenes
curl http://localhost:5050/api/lw/stories/$STORY_ID/cruxes
# Expected: 200, empty array []

# Open non-existent TreeSheets file
curl -X POST http://localhost:5050/api/lw/stories/$STORY_ID/stage4/open_file \
  -H "Content-Type: application/json" \
  -d '{"filepath": "/nonexistent/file.tsv"}'
# Expected: 500 with error message

# Delete story
curl -X DELETE http://localhost:5050/api/lw/stories/$STORY_ID
# Expected: 200

# Get deleted story
curl http://localhost:5050/api/lw/stories/$STORY_ID
# Expected: 404
```

User actions:
- Create a story → confirm it appears in Pipeline Dashboard with empty progress bar.
- Enter Stage 2 → add 1 character → try to mark stage complete → confirm 409 toast.
- Add second character → mark stage complete → confirm advance to Stage 3.
- Click **Show example** on a Stage 2 field → confirm example appears → click again → confirm it hides.
- Stage 5: add 3 scenes → toggle Crux View → confirm only slug line + crux visible.
- Stage 5: add a Descriptionary entry under 50 words → confirm warning shown.
- Stage 7: click Export → confirm file download.
- Mark Draft Complete → switch to Hub → confirm Living Writer card count updates.

## 4.4 Promotion Machine — Contacts

```bash
# Create contact
curl -X POST http://localhost:5050/api/promo/contacts \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Dlamini", "phone": "+27821234567", "tags": ["golf-day"]}'
# Expected: 201

# Duplicate phone
curl -X POST http://localhost:5050/api/promo/contacts \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Again", "phone": "+27821234567"}'
# Expected: 409

# Invalid phone
curl -X POST http://localhost:5050/api/promo/contacts \
  -H "Content-Type: application/json" \
  -d '{"name": "Bad Phone", "phone": "0821234567"}'
# Expected: 400

# Filter by tag
curl http://localhost:5050/api/promo/contacts/by_tag/golf-day
# Expected: 200, array containing Jane Dlamini

# Delete contact
CONTACT_ID=<id>
curl -X DELETE http://localhost:5050/api/promo/contacts/$CONTACT_ID
# Expected: 200

# Confirm leads also deleted
curl http://localhost:5050/api/promo/leads?contact_id=$CONTACT_ID
# Expected: 200, empty array
```

## 4.5 Promotion Machine — Leads

```bash
CONTACT_ID=<valid contact id>

# Create lead
curl -X POST http://localhost:5050/api/promo/leads \
  -H "Content-Type: application/json" \
  -d '{"contact_id": "'$CONTACT_ID'", "product": "Golf Day 2026", "product_type": "event"}'
# Expected: 201

LEAD_ID=<id>

# Advance stage
curl -X PUT http://localhost:5050/api/promo/leads/$LEAD_ID \
  -H "Content-Type: application/json" \
  -d '{"stage": "qualified"}'
# Expected: 200

# Invalid stage
curl -X PUT http://localhost:5050/api/promo/leads/$LEAD_ID \
  -H "Content-Type: application/json" \
  -d '{"stage": "dormant"}'
# Expected: 400

# Log communication
curl -X POST http://localhost:5050/api/promo/leads/$LEAD_ID/log_communication \
  -H "Content-Type: application/json" \
  -d '{"direction": "outbound", "message": "Hi Jane, are you coming to the golf day?"}'
# Expected: 200

# Get lead with log
curl http://localhost:5050/api/promo/leads/$LEAD_ID
# Expected: 200, communication_log has 1 entry
```

## 4.6 Promotion Machine — Message Maker

```bash
curl -X POST http://localhost:5050/api/promo/message_maker/generate \
  -H "Content-Type: application/json" \
  -d '{"purpose": "Invite people to a charity golf day on 15 April", "event_name": "Charity Golf Day", "event_date": "15 April 2026", "target_audience": "business community contacts"}'
# Expected: 200, { "message": "string between 50-120 words" }

# Missing purpose
curl -X POST http://localhost:5050/api/promo/message_maker/generate \
  -H "Content-Type: application/json" \
  -d '{"event_name": "Golf Day"}'
# Expected: 400
```

## 4.7 Promotion Machine — Book Serializer

```bash
BOOK_ID=<id of created book>

# Paste ingest
curl -X POST http://localhost:5050/api/promo/books/$BOOK_ID/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "It was a dark night. The rain came down hard...[500+ words of fiction]", "input_type": "paste"}'
# Expected: 200, chunks array with 2+ items, each under 400 words

# Ingest empty text
curl -X POST http://localhost:5050/api/promo/books/$BOOK_ID/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "", "input_type": "paste"}'
# Expected: 400

# Queue a chunk
CHUNK_ID=<id of first chunk>
curl -X POST http://localhost:5050/api/promo/books/$BOOK_ID/chunks/$CHUNK_ID/queue \
  -H "Content-Type: application/json" \
  -d '{"scheduled_at": null}'
# Expected: 200, message_id returned

# Queue same chunk again
curl -X POST http://localhost:5050/api/promo/books/$BOOK_ID/chunks/$CHUNK_ID/queue \
  -H "Content-Type: application/json" \
  -d '{"scheduled_at": null}'
# Expected: 409
```

## 4.8 Promotion Machine — WA Post Maker

```bash
# Add proverb
curl -X POST http://localhost:5050/api/promo/proverbs \
  -H "Content-Type: application/json" \
  -d '{"text": "Umuntu ngumuntu ngabantu.", "origin": "Zulu"}'
# Expected: 201

# Generate post (requires image_gen configured or returns 503)
curl -X POST http://localhost:5050/api/promo/wa_post/generate
# Expected: 503 if image_gen not configured; 200 with post_content if configured

# Generate with no unused proverbs (after marking all as used)
curl -X POST http://localhost:5050/api/promo/wa_post/generate
# Expected: 409
```

## 4.9 Promotion Machine — Sender

```bash
# Queue a test message manually
curl -X POST http://localhost:5050/api/promo/messages/bulk \
  -H "Content-Type: application/json" \
  -d '{"tag": "golf-day", "content": "Hi {name}, reminder about the golf day.", "scheduled_at": null}'
# Expected: 200, batch_id, message_count > 0

# Process queue (Cowork must be running)
curl -X POST http://localhost:5050/api/promo/sender/process_queue
# Expected: 200, { "processed": N, "failed": 0 }

# Check message status
curl http://localhost:5050/api/promo/messages?status=sent
# Expected: processed messages appear here
```

User actions:
- Set a message with scheduled_at in the past → restart app → confirm overdue banner appears.
- Click **Process Overdue** → confirm messages processed.

---

# SECTION 5 — IMPLEMENTATION ORDER

Build in this sequence. Each phase is a shippable increment — test fully before proceeding to the next.

## Phase 1 — Navigation Restructure (no new functionality)
**Why first:** Everything else depends on the new navigation frame being in place.
1. Restructure `index.html` tab bar into the new hub navigation.
2. Add `currentTopTab` to state in `app.js`.
3. Wrap all existing module renders under the TO-DO tab.
4. Confirm all existing functionality still works identically under the new navigation.
5. Add stub placeholder panels for HUB, LIVING WRITER, PROMOTION MACHINE (just a heading and "Coming soon").

## Phase 2 — Hub
**Why second:** Requires the nav frame. Depends on other modules only for summary counts, which can start at 0.
1. Add `GET /api/hub/summary` to `app.py`.
2. Build Hub view with four cards reading from the summary endpoint.
3. Wire Open buttons to tab switches.

## Phase 3 — Living Writer (Stages 1–4)
**Why third:** Standalone. No dependencies on Promotion Machine.
1. Add `LIVING_WRITER_FILE` constant and `migrate()` step.
2. Implement all story CRUD routes.
3. Build Pipeline Dashboard view.
4. Build Story Detail view with stage sidebar.
5. Implement Stage 1 panel (concept note + DEVONthink nudge).
6. Implement Stage 2 panel (Character Arc Outlines + Fragments + World's Rules + Leviathan). Include toggleable field examples.
7. Implement Stage 3 panel (Arc Brainstorm + Logline generation + TSV copy).
8. Implement Stage 4 panel (TreeSheets file linking + open).
9. Wire the existing "Start a LivingWriter record?" stub to open Living Writer and pre-populate.

## Phase 4 — Living Writer (Stages 5–7 + Anki export)
1. Implement Stage 5 panel (Treatment scenes with drag-and-drop reorder + Crux View + Descriptionary).
2. Implement Stage 6 panel (Narrative Summary + Anki export + Reconstruction log).
3. Implement Stage 7 panel (Export targets + Mark Draft Complete).
4. Implement `POST /api/lw/stories/<id>/complete` with Indaba signal.
5. Verify Hub summary updates on draft-complete.

## Phase 5 — Promotion Machine: Contacts & Leads (CRM)
**Why before content tools:** Contacts are referenced by the message queue and content tools. Build the data foundation first.
1. Add all promo storage files and `migrate()` steps.
2. Implement all contact routes.
3. Implement all lead routes.
4. Build CONTACTS sub-tab (table, add modal, CSV import, contact detail panel).
5. Build LEADS sub-tab (kanban board, lead detail, communication log, compose + send/schedule).
6. Wire the existing "Add to the CRM?" stub.

## Phase 6 — Promotion Machine: Content Creator
1. Implement Message Maker route + sub-tab.
2. Implement Book Serializer routes + sub-tab (paste and file upload).
3. Implement Proverbs routes.
4. Implement WA Post Maker generate route (with 503 guard for unconfigured image gen) + sub-tab.
5. Implement Promo Settings route + SETTINGS sub-tab (AI provider config, CTA links, branding).

## Phase 7 — Promotion Machine: Message Queue & Sender
1. Implement message queue routes (list, reschedule, delete).
2. Implement bulk message route.
3. Implement `process_overdue_queue()` helper in `migrate()`.
4. Implement Cowork file-based job handoff (write job file, poll result file, update message status).
5. Implement `POST /api/promo/sender/process_queue` and `send_now`.
6. Build SENDER sub-tab (queue table, overdue banner, process controls).

## Phase 8 — Image Generation Integration
**Why last:** Requires external API credential the user must supply. All other features work without it.
1. Implement generic image gen HTTP POST using `promo_settings.ai_providers.image_gen.endpoint`.
2. Connect to WA Post Maker generate route.
3. Test with the user's chosen provider (e.g., Kimi Moonshot).

---

# OPEN DECISIONS LOG

All items tagged `[DECISION NEEDED]` in the body of this brief, consolidated here for reference:

1. **LivingWriter → Indaba signal matching** (Section 3.1): Should the signal match on story title or on an explicit `indaba_project_id` field on the story? Recommended: add `indaba_project_id` field and populate it from the stub flow.

2. **WhatsApp Web contact import** (Section 2.3.10, CONTACTS sub-tab): The mechanism for importing contacts directly from WhatsApp Web is not technically specified. Implement manual + CSV import only in v1. Flag WhatsApp Web import as a future feature.

3. **Cowork job pickup mechanism** (Section 2.3.8): Does Cowork watch `/data/cowork_jobs/` for new files, or does Indaba call a Cowork API endpoint? The brief assumes file-based handoff. Confirm or replace before building Phase 7.

4. **"Queue All Pending" interval scheduling** (Section 2.3.6, Book Serializer): Proposed mechanism is a modal asking for start date/time and interval in days. Confirm this is the desired behaviour before building.

5. **Image generation provider** (Section 2.3.7, WA Post Maker): Provider endpoint, request format, and response format are not yet specified. The brief assumes a generic `POST { "prompt": string }` → `{ "url": string }` contract. Confirm or adjust when the user supplies the Kimi Moonshot (or equivalent) API documentation.
