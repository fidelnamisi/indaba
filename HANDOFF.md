# Indaba — Handoff Document
**Last updated:** 2026-04-16
**Session summary:** Designed the Panorama mode UI. No code was written — this was a pure design session. The full data model and display logic for Panorama is now agreed and documented below.

---

## HOW TO START THE NEXT SESSION

### Standard mode:
```bash
cd /Users/fidelnamisi/Indaba
claude
```

### With full permissions:
```bash
cd /Users/fidelnamisi/Indaba
claude --dangerously-skip-permissions
```

Claude Code reads `CLAUDE.md` (project instructions) and `indaba-sla.md` (SLA) on startup. This `HANDOFF.md` gives the session context.

---

## ⚡ FIRST TASK NEXT SESSION — BUILD PANORAMA MODE

The design is fully agreed. Build it. Reference the Miro board for visual layout:
**https://miro.com/app/board/uXjVGh5GEy8=**

---

## PANORAMA MODE — AGREED DESIGN

### Philosophy
Panorama is a single-screen dashboard that shows the status of every chapter across three parallel workflows: Production, Publishing, and Promotion. It is the "control tower" view — you can see at a glance what's done, what's pending, and where things are out of sync.

### Layout
Three persistent vertical panels side by side:

| Production | Publishing | Promotion |
|---|---|---|
| Blue header | Green header | Purple header |
| Asset → Revision → Status | Platform → Revision → Status | Campaign → Revision → Status |

### Row hierarchy (toggles)
```
▼ ROTRQ  (book/work level — toggle collapses all chapters)
  ▼ Chapter 1  (chapter level — toggle collapses assets/platforms/campaigns)
    [Production]   Prose      Rev 1  ✓
                   Blurb      Rev 1  ✓
                   Tagline    Rev 1  ✓
                   Header     Rev 1  ✓
    [Publishing]   ▼ website        Rev 1  ⚠️
                       Prose        Rev 1  ✓
                       Blurb        Rev 1  ✓
                       Tagline      Rev 1  ✓
                       Header       Rev 1  ✗  ← pending
                   ▼ patreon        Rev 2  ✓
                       Prose        Rev 1  ✓
                       Blurb        Rev 1  ✓
                       Tagline      Rev 1  ✓
                       Header       Rev 2  ✓  ← updated
    [Promotion]    WA Serialization  Rev 1  ✓
                   Social            Rev 1  ✗
```

### Panel depths
- **Production**: 2 levels — Chapter → Assets (Prose, Blurb, Tagline, Header)
- **Publishing**: 3 levels — Chapter → Platform (website, patreon) → Assets. Platform row shows summary status (⚠️ if any asset lags). Expand to see per-asset breakdown.
- **Promotion**: 2 levels — Chapter → Campaigns (WA Serialization, Social). No third level — a campaign always promotes the whole chapter as a unit.

### Sub-column headers
- Production: Asset | Revision | Status
- Publishing: Platform | Revision | Status
- Promotion: Campaign | Revision | Status

### Status indicators
- ✓ = complete/published/sent
- ✗ = pending/not done
- ⚠️ = partial (summary level only — used on Publishing platform rows when assets are mixed)

### Filter bar
- All Books dropdown
- Any Status dropdown
- Search input

### Header
- Title: "Chapter Publishing & Promotion"
- Search box (top right)
- "+ Add Chapter" button (top right)

### Footer
- "Showing N books, N chapters"
- Pagination controls

---

## PREVIOUS SESSION FIRST TASK (still open) — TEST & WIRE UP CRM

The People/CRM mode was built this session and needs testing before it's considered production-ready. Start the next session by restarting the server and running through this checklist:

### 1. Contacts tab
- [ ] Add a contact manually (name + phone + email)
- [ ] Import a CSV (use the format: `Number,Name,email` — same as the test file in `/Users/fidelnamisi/Github/laravel-crm/import test1.csv`)
- [ ] Search/filter contacts
- [ ] Open a contact panel and verify leads are shown

### 2. Pipeline tab
- [ ] Create a lead from a contact (Retreat pipeline + Subscription pipeline)
- [ ] Verify Kanban board shows the lead in the correct stage column
- [ ] Move a lead to a different stage
- [ ] Mark a lead as Won / Lost
- [ ] Mark a Subscription lead as Cancelled (post-win)
- [ ] Re-open a closed lead

### 3. Outreach tab — MESSAGE SENDING (critical)
- [ ] Open a lead, type a message, click **"Send via WA"** — verify GOWA delivers it to the contact's phone
- [ ] Check that the message appears in the communication log
- [ ] Open the **"Log Message"** button on Outreach tab, pick a contact + lead, log manually
- [ ] Verify the manual entry appears in the Outreach weekly table
- [ ] Click "Copy Weekly Report" and verify the clipboard text is formatted correctly
- [ ] Click the target number to edit the weekly target — verify it saves and persists

### 4. Dashboard tab
- [ ] After creating some Won/Lost leads with values, verify revenue figures show correctly
- [ ] Verify pipeline stage breakdown bars render correctly

---

## WHAT WAS BUILT THIS SESSION

### Scheduler (ENFORCED META-SCHEDULE v2)
- **Backend:** `routes/scheduler_agent.py`
- **Endpoints:** `GET /api/scheduler/preview`, `POST /api/scheduler/run`, `GET/POST /api/scheduler/clean-queue`
- **UI:** PROMOTING → Outbox tab — "Preview Schedule", "Run Scheduler", "Audit Queue", "Clean Queue" buttons
- **Slot times (SAST):** Mon–Sat 07:30 PROVERB · 12:15 NOVEL_SERIAL · 18:30 FLASH_FICTION; Sun 09:00 PROVERB
- **EC2 queue was cleaned:** 2 wrong times fixed, 4 duplicates deleted

### CRM People Mode
- **Backend:** `routes/crm_people.py` — full CRUD for contacts, leads, pipelines, outreach KPI, dashboard
- **Data files:** `data/crm_contacts.json` (migrated from promo_contacts.json), `data/crm_leads.json`, `data/crm_pipelines.json`, `data/crm_settings.json`
- **Pipelines:**
  - Retreat (Event): Enquiry → Qualified → Proposal Sent → Negotiation → Confirmed/Lost
  - Subscription: Enquiry → Qualified → Negotiation → Won/Lost/Cancelled
- **4 tabs in People mode:** Contacts · Pipeline (Kanban) · Outreach (KPI + weekly report) · Dashboard
- **Communication log:** per lead, logged_via crm (sends via GOWA) or manual
- **Weekly outreach report:** copy-pasteable text for stickk.com accountability

### Key API endpoints
```
GET/POST  /api/crm/contacts
POST      /api/crm/contacts/import     (CSV upload)
GET/PUT/DELETE /api/crm/contacts/<id>
GET/POST  /api/crm/leads
GET/PUT/DELETE /api/crm/leads/<id>
PUT       /api/crm/leads/<id>/stage
POST      /api/crm/leads/<id>/close    { outcome: won|lost|cancelled }
POST      /api/crm/leads/<id>/reopen
POST      /api/crm/leads/<id>/messages (log outreach)
DELETE    /api/crm/leads/<id>/messages/<msg_id>
GET       /api/crm/pipelines
GET/PUT   /api/crm/settings
GET       /api/crm/outreach/weekly     (?week_start=YYYY-MM-DD)
GET       /api/crm/outreach/report
GET       /api/crm/dashboard
```

---

## KNOWN OPEN ITEM

**Proverbs have no generated images** — 213 proverbs exist in promo_proverbs.json with `queue_status: null` but none have `composite_path` set (no generated images). The scheduler skips them. Images need to be generated before the PROVERB slots will be filled. This is a separate workflow (image generation for each proverb).

---

## ARCHITECTURE QUICK REFERENCE

| Layer | Detail |
|-------|--------|
| Backend | Python/Flask, port 5050, `app.py` |
| Frontend | Vanilla JS, `static/app.js` (~11k lines) |
| Styles | `static/style.css` |
| Data | JSON files in `data/`, atomic writes via `os.replace()` |
| EC2 Sender | `http://13.218.60.13:5555` — scheduled WA delivery |
| GOWA | `EC2_SENDER_URL` env var, device `GOWA_DEVICE_ID` |

## 5-MODE NAV

| Mode | Purpose |
|------|---------|
| PANORAMA | Grid overview of all pipeline modules |
| PRODUCING | Pipeline · Flash Fiction · Proverbs |
| PUBLISHING | Website publishing workflow |
| PROMOTING | Works (serializer) · Outbox (scheduler + EC2) |
| PEOPLE | Contacts · Pipeline · Outreach · Dashboard |
