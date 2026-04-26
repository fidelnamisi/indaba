# Phase 1 Handoff — Discord Bot Tools Expanded
**Date:** 2026-04-26
**Session commit:** `b3e9a4a`
**Phase:** 1 of 5 — Add 10 new tools to Discord bot

---

## What Was Done

### 1. Pre-flight QA (Haiku agent)
All Phase 0 checks re-run and passed:
- All 3 services active (indaba-app, indaba-discord, indaba-sender)
- All 9 smoke-test routes returning expected HTTP codes
- All env vars present, data counts correct (74 pipeline entries, 258 proverbs)
- GitHub token valid

### 2. 10 new tools added

**Files modified:**
- `discord_bot/claude_agent.py` — 10 new entries in `TOOLS` list, 10 new cases in `_execute_tool()`
- `discord_bot/indaba_client.py` — 10 new client functions

| Tool | Endpoint | Command it enables |
|------|----------|--------------------|
| `works_list_modules` | `GET /api/works/<id>` | "Show Love Back chapters" |
| `work_queue_module` | `POST /api/works/<id>/modules/<id>/queue` | "Queue chunk 3 for WA" |
| `scheduler_run` | `POST /api/scheduler/run` | "Fill the schedule" |
| `scheduler_preview` | `GET /api/scheduler/preview` | "Show next 14 days of content" |
| `proverbs_create_batch` | `POST /api/promo/proverbs/import_bulk` | "Create 5 new proverbs" |
| `flash_fiction_generate` | `POST /api/flash-fiction/generate` | "Create flash fiction" |
| `flash_fiction_publish_queue` | website_publish → URL → work_queue_module | "Publish + add website link as CTA" |
| `audio_browse` | `GET /api/audio/browse/<work_id>` | "Show OAO audio files" |
| `audio_upload` | `POST /api/audio/upload` | "Connect Chapter 5 audio" |
| `crm_leads_summary` | `GET /api/promo/pipeline` | "How many open leads?" |

### 3. Deploy
- Both files SCP'd to `/opt/indaba-discord/`
- `indaba-discord` restarted → confirmed active

### 4. Route smoke tests (all pass)

| Route | Expected | Result |
|-------|----------|--------|
| `GET /api/scheduler/preview` | 200 | ✅ PASS |
| `POST /api/scheduler/run` (dry_run) | 200 | ✅ PASS |
| `GET /api/works` | 200 | ✅ PASS |
| `GET /api/works/<id>` | 200 + correct data | ✅ PASS |
| `GET /api/promo/pipeline` | 200 | ✅ PASS |
| `GET /api/audio/browse/OAO` | 200 | ✅ PASS |
| `POST /api/promo/proverbs/import_bulk` | 200 | ✅ PASS |
| `POST /api/flash-fiction/generate` (empty body) | 400 | ✅ PASS |

### 5. GitHub push
Commit `b3e9a4a` pushed to `github.com/fidelnamisi/indaba`

---

## EC2 Service Status (post-Phase 1)

| Service | Status | Port |
|---------|--------|------|
| `indaba-app` | ✅ active | 5050 |
| `indaba-discord` | ✅ active | — |
| `indaba-sender` | ✅ active | 5555 |

---

## Data State

| Store | EC2 count |
|-------|-----------|
| Pipeline entries | 74 |
| Proverbs | 258 total |
| Works | 5 (Love Back Ch4, Last December, Adderley, Setshego, Love Back) |

---

## Known Remaining Issues (carried from Phase 0)

1. **pCloud folder paths** — `audio_browse` returns empty on EC2 because pCloud is not mounted. `audio_upload` will similarly fail for local file lookup. Audio must be tested locally or with S3 URL overrides.

2. **EC2 `promo_settings.json` has empty `ai_providers: {}`** — falls back to DeepSeek, which works.

3. **`macos_contacts` route** — will fail gracefully on EC2 (not a Mac). Not a blocker.

4. **`proverbs_remaining: 0` in scheduler** — All 258 proverbs lack `composite_path`, so the scheduler finds none ready. Proverb images must be generated (via `promo_broadcast_generate`) before scheduling. This is expected behaviour.

---

## What Phase 2 Should Focus On

**Priority: End-to-end workflow testing via Discord**

With all tools now in place, Phase 2 is about making them compose reliably when triggered from Discord natural-language commands. Suggested test commands:

1. `Show me all the chapters of Love Back Chapter 4` → tests `works_list_modules`
2. `Show me the next 14 days of scheduled content` → tests `scheduler_preview`
3. `Create 3 new African proverbs about perseverance` → tests `proverbs_create_batch` (Claude generates text, tool imports)
4. `Generate a 300-word fantasy flash fiction set in 1890s Lagos` → tests `flash_fiction_generate`
5. `How many open leads do I have?` → tests `crm_leads_summary`
6. `Fill the content schedule` → tests `scheduler_run`

**Secondary: CRM sync investigation**
The handoff notes that "sync all messages from all leads" requires GoWA incoming message sync. This needs investigation in Phase 2:
- Check what data `indaba-sender` webhook receiver stores
- Determine if a pull route exists in `routes/promo_messages.py`

**Tertiary: proverb image pipeline**
Proverbs can't be scheduled until they have `composite_path`. The workflow is:
1. `promo_broadcast_generate` — generates AI caption + image prompt, triggers Imagen 3
2. Check proverb has `composite_path` set
3. `scheduler_run` — picks it up

This is already working but needs a Discord-driven test.

---

## SSH Access

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
```

EC2 IP: `13.218.60.13`
Key: `~/Indaba/ec2-key.pem`
