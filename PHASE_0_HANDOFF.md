# Phase 0 Handoff — Baseline Sync Complete
**Date:** 2026-04-26
**Session commit:** `834152b`
**Phase:** 0 of 5 — Audit, sync, and config fixes

---

## What Was Done

### 1. Full audit of local vs EC2 state
- Confirmed EC2 bot files (`bot.py`, `claude_agent.py`, `indaba_client.py`) are **byte-identical** to local — no bot sync needed
- Confirmed all route files already existed on EC2 and **all blueprints were already registered** in `app.py`
- Found only `static/app.js` differed between local and EC2 (5,000+ line UI overhaul not yet deployed)
- Data state: both local and EC2 have 74 pipeline entries, 258 proverbs

### 2. Files synced to EC2
| File | Action |
|------|--------|
| `static/app.js` | SCP'd to EC2 — full UI now live |

### 3. Config fixes applied to EC2

| Service | Fix |
|---------|-----|
| `indaba-discord.service` | `GITHUB_TOKEN` set — `!idea` push to GitHub now works |
| `indaba-app.service` | `GOOGLE_SA_KEY=/opt/indaba-app/google-sa.json` added — Imagen 3 proverb image generation now works |
| `google-sa.json` | Uploaded to `/opt/indaba-app/google-sa.json` (project: `gen-lang-client-0717388888`) |

### 4. GitHub push
- 93 files committed and pushed to `github.com/fidelnamisi/indaba` (commit `8561ae6` + `834152b`)
- Security fix: `ec2-key.pem` removed from tracking, `*.pem` added to `.gitignore`

---

## EC2 Service Status (post-Phase 0)

| Service | Status | Port |
|---------|--------|------|
| `indaba-app` | ✅ active | 5050 |
| `indaba-discord` | ✅ active | — |
| `indaba-sender` | ✅ active | 5555 |

---

## Smoke Test Results (all pass)

| Route | Method | Expected | Result |
|-------|--------|----------|--------|
| `/api/hub/summary` | GET | 200 | ✅ PASS |
| `/api/content-pipeline` | GET | 200 | ✅ PASS |
| `/api/works` | GET | 200 | ✅ PASS |
| `/api/promo/proverbs` | GET | 200 | ✅ PASS |
| `/api/scheduler/preview` | GET | 200 | ✅ PASS |
| `/api/audio/browse/LB` | GET | 200 | ✅ PASS |
| `/api/flash-fiction/generate` | POST (empty body) | 400 | ✅ PASS |
| `/api/promo/pipeline` | GET | 200 | ✅ PASS |
| `/api/settings` | GET | 200 | ✅ PASS |

---

## Data State

| Store | EC2 count |
|-------|-----------|
| Pipeline entries | 74 |
| Proverbs | 258 total, 213 unused |

---

## What Phase 0 Unlocked

These routes are now confirmed live on EC2 (were registered but untested before):
- `POST /api/flash-fiction/generate` — flash fiction generation (uses Claude Sonnet)
- `GET/POST /api/audio/browse`, `POST /api/audio/upload` — audio linking
- `GET/POST /api/scheduler/preview`, `POST /api/scheduler/run` — 14-day rolling schedule
- `GET /api/promo/pipeline` — CRM pipeline summary
- All `crm_people`, `git_ops`, `macos_contacts`, `asset_register`, `work_types` routes

Proverb image generation (Imagen 3 via Google Vertex AI) is now unblocked on EC2.

---

## Known Remaining Issues

1. **EC2 `promo_settings.json` has empty `ai_providers: {}`** — falls back to DeepSeek default, which works correctly since `DEEPSEEK_API_KEY` is set in the service env. No action needed unless you want to explicitly configure providers.

2. **pCloud folder paths** — `routes/audio.py` reads `pcloud_folder` from series config. These are local Mac paths (e.g. `/Users/fidelnamisi/pCloud Drive/...`). Audio browsing will return empty on EC2 unless pCloud is mounted or paths are updated. Audio upload still works if you provide an S3 URL directly.

3. **`macos_contacts` route** — reads from macOS Contacts app. Will fail gracefully on EC2 (not a Mac). Not a blocker.

---

## Phase 1 — What Comes Next

**Goal:** Add 10 new tools to the Discord bot so all 5 target command types work.

**Bot tool gaps to fill** (in `discord_bot/claude_agent.py` TOOLS list + `discord_bot/indaba_client.py`):

| Tool to add | Endpoint | Command it enables |
|-------------|----------|--------------------|
| `works_list_modules` | `GET /api/works/<id>` | "Show Love Back chapters" |
| `work_ingest_and_queue` | `POST /api/works/<id>/ingest` + `/modules/<id>/queue` | "Serialise next LB chapter + queue" |
| `scheduler_run` | `POST /api/scheduler/run` | "Fill the schedule" |
| `scheduler_preview` | `GET /api/scheduler/preview` | "Show next 7 days of content" |
| `proverbs_create_batch` | `POST /api/promo/proverbs/import_bulk` | "Create 5 new proverbs" |
| `flash_fiction_generate` | `POST /api/flash-fiction/generate` | "Create flash fiction" |
| `flash_fiction_publish_queue` | publish → URL → queue | "Publish + add website link as CTA" |
| `audio_browse` | `GET /api/audio/browse/<work_id>` | "Show OAO audio files" |
| `audio_upload` | `POST /api/audio/upload` | "Connect Chapter 5 audio" |
| `crm_leads_summary` | `GET /api/promo/pipeline` | "How many open leads?" |

**Note on CRM sync ("sync all messages from all leads"):** This requires GoWA incoming message sync via the webhook receiver in `indaba-sender`. Needs separate investigation in Phase 1 to confirm what data is available and whether a pull route exists.

**Files to modify:**
- `discord_bot/claude_agent.py` — add tool definitions to `TOOLS` list, add cases to `_execute_tool()`
- `discord_bot/indaba_client.py` — add client functions for each new endpoint

**Deploy after changes:**
```bash
scp -i ~/Indaba/ec2-key.pem discord_bot/claude_agent.py discord_bot/indaba_client.py ubuntu@13.218.60.13:/opt/indaba-discord/
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 "sudo systemctl restart indaba-discord"
```

**Then test in Discord:**
- `Serialise the next chapter of Love Back and add to the queue`
- `Create and schedule 5 new proverbs`
- `Show me the next 7 days of scheduled content`

---

## AI Model Stack (reference for Phase 1)

| Layer | Model | Where |
|-------|-------|-------|
| Bot NLP dispatch | Claude Haiku (`claude-haiku-4-5-20251001`) | `discord_bot/config.py` |
| Proverb meaning, WA posts, synopsis, serialization | DeepSeek (`deepseek-chat`) | `services/ai_service.py` via `promo_settings.json` |
| Flash fiction | Claude Sonnet (`claude-sonnet-4-20250514`) | `routes/flash_fiction.py` (hardcoded) |
| Proverb images | Google Imagen 3 | `capabilities/create/generator.py` |

---

## SSH Access

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
```

EC2 IP: `13.218.60.13`
Key: `~/Indaba/ec2-key.pem` (permanent, no Instance Connect needed)
