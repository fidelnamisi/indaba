# Multi-Agent Coordination — Realms and Roads Publishing System
**Created:** 2026-03-31
**Purpose:** Prevent overlap and merge conflicts when multiple Claude Code agents work on Indaba and realmsandroads.com simultaneously.

---

## How To Use This Document

**This is the master coordination hub.** Each agent gets its own focused HANDOFF.md, but they read THIS document first to understand the division of labor.

**If you are a coding agent:**
1. Read this document first
2. Identify which **PROJECT** you own (Indaba or realmsandroads.com)
3. Read your project's HANDOFF.md for implementation details
4. Complete ONLY the tasks marked for your project
5. Do NOT modify files in the other project

---

## Project Split

There are **two separate projects** that need to work together:

| Project | Root Directory | Responsibility | When to Start |
|---------|----------------|-----------------|---|
| **Indaba** | `/Users/fidelnamisi/Indaba` | Content management dashboard, chapter publishing orchestration | After realmsandroads.com is deployed |
| **realmsandroads.com** | `/Users/fidelnamisi/28\ Titles/1.\ WIP/realmsandroads.com` | Static website, Lambda APIs, chapter hosting | START FIRST — blocks Indaba work |

---

## Task Allocation by Agent

### AGENT 1: realmsandroads.com (Website)

**Folder to run Claude Code from:**
```bash
cd /Users/fidelnamisi/28\ Titles/1.\ WIP/realmsandroads.com
claude
```

**Read:** This folder's HANDOFF.md (create one if it doesn't exist — see Section 5 below)

**Tasks (in order):**

1. ✅ **UX Completeness Audit (DONE)** — session expiry, error states, audio fixes, nav cleanup, series links. Changes made to:
   - `public/account.html`
   - `public/join.html`
   - `public/search.html` + `public/js/search.js`
   - `public/js/chapter-gate.js`
   - `public/js/rr-auth.js`
   - All 58 chapter HTML files
   - 8 other static pages

2. ⏳ **SAM Deploy** (HIGH PRIORITY — do immediately)
   - Run: `sam build && sam deploy` from root
   - What it picks up: new `SesFromEmail` param, any Lambda route changes
   - Estimated time: 10–15 minutes
   - **BLOCKS:** Indaba publishing won't work without this

3. ⏳ **Website Redeploy** (HIGH PRIORITY — do after SAM)
   - Run: `bash redeploy.sh` from root (or use amplify-deploy Cowork skill)
   - What it does: pushes all UX changes to Amplify
   - Estimated time: 3–5 minutes
   - **UNBLOCKS:** Indaba can now publish to a live website

4. ⏳ **Paystack Webhook** (MEDIUM PRIORITY — manual, Fidel does this)
   - Add to Paystack dashboard: `https://jk9fz38v33.execute-api.us-east-1.amazonaws.com/api/webhook/paystack`
   - **Dependency note:** Lambda routes already support webhooks; this is config-only

5. ⏳ **Go-Live Prep** (LOW PRIORITY — when ready for real payments)
   - Switch Paystack test keys → live keys in Lambda env vars
   - Verify SES sender email
   - Test a real payment end-to-end

**STOP HERE.** Do not touch Indaba files.

---

### AGENT 2: Indaba (Publishing Dashboard)

**Folder to run Claude Code from:**
```bash
cd /Users/fidelnamisi/Indaba
claude
```

**Read:** `HANDOFF.md` in this folder

**Tasks (in order):**

1. ⏳ **Wait for Agent 1 to complete Tasks 2–3** (SAM + Redeploy)
   - You cannot test your publish buttons until the website is live
   - Check status: navigate to `http://localhost:5050`, Settings tab, click "Test Connection"
   - Should return green ✓ when realmsandroads.com is deployed

2. ✅ **Backend Infrastructure (DONE)** — all routes exist:
   - `routes/website_publisher.py` — publish + batch publish
   - `services/chapter_html_template.py` — HTML generator
   - Data migrations — prose/author_note/header_image fields added
   - No code changes needed; do not touch these files

3. ⏳ **Frontend Fix Checklist** (HIGH PRIORITY)
   - Tasks are in `HANDOFF.md`, Section 5–6
   - Edit `templates/index.html` — add Publishing tab
   - Edit `static/app.js` — wire up Publishing tab, fix Settings form
   - ~200 lines of changes total
   - Estimated time: 45–60 minutes
   - **UNBLOCKS:** Users can see Publish buttons and Settings

4. ⏳ **Feature 2: Audio Publishing** (MEDIUM PRIORITY — deferred)
   - New routes: `routes/audio_publisher.py`
   - Pre-read: `lambda/routes/audio.js` in the website folder
   - Full spec: `WEBSITE_PUBLISHING_BRIEF.md`, Section Feature 2
   - Estimated time: 2 hours
   - Can be done in parallel with realmsandroads.com tasks 4–5

5. ⏳ **QA Checklist** (when features are done)
   - Publish a test chapter (add prose, header image, hit Publish)
   - Verify HTML appears at `realmsandroads.com/public/chapters/`
   - Verify `chapters.json` updated
   - Verify site is still accessible after deploy

**STOP HERE.** Do not touch realmsandroads.com files.

---

## Dependencies and Blocking

```
Website (Agent 1) → Indaba (Agent 2)
        ↓
   SAM deploy (picks up Lambda changes)
        ↓
   Redeploy to Amplify (pushes static site)
        ↓
   [NOW realmsandroads.com is LIVE]
        ↓
   Indaba can test Publishing feature
   (test connection will pass)
        ↓
   Indaba frontend fixes are testable
   (publish buttons actually work)
```

**Critical:** Indaba's frontend cannot be tested until the website is deployed. Agent 2 should wait for Agent 1 to complete Tasks 2–3 before attempting QA.

---

## File Territories (Do Not Cross)

### Agent 1 (Website) owns:
```
/Users/fidelnamisi/28 Titles/1. WIP/realmsandroads.com/
  ├── public/                         [EDIT]
  ├── lambda/                         [EDIT]
  ├── template.yaml                   [READ ONLY — do not edit]
  ├── redeploy.sh                     [READ ONLY — do not run manually]
  └── (other files are safe to touch)
```

### Agent 2 (Indaba) owns:
```
/Users/fidelnamisi/Indaba/
  ├── routes/                         [EDIT]
  ├── services/                       [EDIT]
  ├── static/                         [EDIT]
  ├── templates/                      [EDIT]
  ├── app.py                          [EDIT]
  ├── data/                           [EDIT — via atomic writes only]
  └── (other files are safe to touch)
```

### Shared Reference (Both read, neither edits):
```
/Users/fidelnamisi/Indaba/
  ├── WEBSITE_PUBLISHING_BRIEF.md     [Both read for context]
  ├── indaba-sla.md                   [Agent 2 uses; Agent 1 reads if curious]
  └── HANDOFF.md                      [Agent-specific]

/Users/fidelnamisi/28 Titles/1. WIP/realmsandroads.com/
  ├── lambda/routes/audio.js          [Agent 2 reads before starting audio feature]
  └── (create HANDOFF.md if needed)
```

---

## Communication Protocol

If Agent 2 discovers a blocker in Agent 1's work:
1. **Do NOT edit Agent 1's files**
2. Add a note to `MULTI-AGENT-COORDINATION.md` (this file), Section "Blockers"
3. Fidel will see it and can relay to Agent 1 or fix manually

If Agent 1 completes its work, update Section 1 of this doc to mark it ✅ DONE so Agent 2 knows to proceed.

---

## Blockers

*(This section is updated as issues arise.)*

Currently: None

---

## Quick Status Check

Agent 2 can check readiness by running this from Indaba:
```python
# In Indaba, navigate to Settings → Website Publishing
# Click "Test Connection"
# If green ✓ "OK" — Agent 1 is done, you can proceed
# If red ✗ "Not configured" — check website_dir path
# If red ✗ "chapters/ not found" — Agent 1 hasn't deployed yet
```

---

## Handoff Locations

| Agent | Project | Handoff Location | Run Command |
|-------|---------|------------------|------------|
| 1 | realmsandroads.com | *(create after first run)* | `cd /Users/fidelnamisi/28\ Titles/1.\ WIP/realmsandroads.com && claude` |
| 2 | Indaba | `/Users/fidelnamisi/Indaba/HANDOFF.md` | `cd /Users/fidelnamisi/Indaba && claude` |

---

## Architecture Principles (Both Agents)

1. **Read before you write** — read existing code before modifying it
2. **Never break existing APIs** — extend, don't replace
3. **Atomic writes only** — use `write_json()` in Indaba; use standard file writes elsewhere
4. **Test in isolation** — if you're not sure a change is safe, ask or create a test
5. **Communicate via this doc** — if you discover something the other agent needs to know, update this file

---

## Next Steps

1. Fidel identifies which agent should start first (usually Agent 1 — website)
2. Each agent reads this file + their project's HANDOFF.md
3. Agents work in parallel on their respective tasks
4. Agent 1 updates this file when Tasks 2–3 are done (SAM + Redeploy) ✅
5. Agent 2 waits for that marker, then proceeds with frontend fixes
6. Both agents test independently in their own project
7. Fidel integrates final result on his Mac

---

## Revision Log

| Date | Change |
|------|--------|
| 2026-03-31 | Document created |

