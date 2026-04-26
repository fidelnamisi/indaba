# Phase 3 Handoff — Batch Generation, Inbound Messages, Data Sync
**Date:** 2026-04-26
**Session commit:** 2b984f9
**Phase:** 3 of 5

---

## What Was Done

### Pre-flight QA (Haiku agent)
All Phase 2 checks re-run and passed:
- All 3 services active (indaba-app, indaba-discord, indaba-sender)
- All routes returning expected HTTP codes
- Tool count: 26 ✓, proverbs: 261 with 45 composite_path ✓
- No fatal errors in Discord bot journal

### 1. Proverb Batch Image Generation

**New route:** `POST /api/promo/broadcast_post/generate_batch`
- Body: `{"limit": N}` (max 50)
- Finds proverbs without `composite_path`, generates AI caption + image for each
- Returns: `{"processed": N, "failed": [{"proverb_id": ..., "error": ...}]}`
- File: `routes/promo_broadcast_post.py`

**New Discord bot tool:** `proverbs_generate_batch`
- Description: "Generate AI captions and images for the next N proverbs that don't yet have a broadcast post"
- Input: `{"limit": integer, default 10}`
- Files: `discord_bot/claude_agent.py`, `discord_bot/indaba_client.py`
- Bot tool count is now **27**

**Note on EC2 image generation:**
- EC2 environment lacks the `google` Python package (no Google Cloud SDK)
- `generate_batch` returns graceful `failed` entries with `"No module named 'google'"`
- Image generation must run locally where Google SDK is installed
- Proverbs with `composite_path` set locally can then be synced to EC2

### 2. GoWA Inbound Message Capture

**New route:** `POST /api/promo/messages/inbound`
- Body: `{"from": "+27...", "body": "...", "timestamp": "..."}`
- Looks up sender phone in `promo_contacts.json`
- Finds active (non-closed, non-lost) lead for that contact
- Appends `{"direction": "inbound", "channel": "whatsapp", "body": ..., "timestamp": ...}` to lead's `communication_log`
- Writes `promo_leads.json` atomically
- Returns `{"ok": true, "lead_id": "...", "contact_found": true/false}`
- Unknown senders: returns `ok: true` with `lead_id: null` (graceful, no crash)
- File: `routes/promo_messages.py`

**Test result:**
```
POST /api/promo/messages/inbound
{"from":"+27822909093","body":"Test inbound message","timestamp":"2026-04-26T12:00:00Z"}
→ {"contact_found":true,"lead_id":"585971a1-7590-4fcf-af5f-543113cd85ec","ok":true}
```

**GoWA webhook config:** GoWA must be pointed at `http://<EC2_IP>:5050/api/promo/messages/inbound` — this is not done yet. GoWA configuration is managed outside this codebase.

### 3. Data Sync Hardening

**New script:** `scripts/sync_to_ec2.sh`
- Pushes `promo_leads.json`, `promo_contacts.json`, `promo_proverbs.json` to EC2 via scp
- Usage: `./scripts/sync_to_ec2.sh`
- Executable (`chmod +x`)

**CLAUDE.md updated** — documents which files are local vs EC2-authoritative:

| File | Authoritative source |
|------|---------------------|
| `promo_leads.json` | Local (push to EC2 after edits) |
| `promo_contacts.json` | Local (push to EC2 after edits) |
| `promo_proverbs.json` | EC2 (bot adds proverbs there) |
| `promo_messages.json` | EC2 (do not overwrite) |
| `content_pipeline.json` | Local only |

**Contacts synced to EC2** this session — EC2 now has 2 contacts.
**Leads synced to EC2** this session — EC2 now has 5 leads.

### 4. EC2 Fix: distribution_service.py

EC2's `distribution_service.py` was missing `fetch_ec2_queue` (deployed in a prior local-only session). Deploying the updated `routes/promo_broadcast_post.py` surfaced this. Fixed by deploying the full local `distribution_service.py` to EC2.

---

## EC2 Service Status (post-Phase 3)

| Service | Status | Port |
|---------|--------|------|
| `indaba-app` | ✅ active | 5050 |
| `indaba-discord` | ✅ active | — |
| `indaba-sender` | ✅ active | 5555 |

---

## Data State

| Store | EC2 count | Notes |
|-------|-----------|-------|
| Proverbs | 261 | 45 with composite_path (image-ready) |
| Leads | 5 | Synced this session |
| Contacts | 2 | Synced this session |
| Bot tools | 27 | +1 from Phase 3 |

---

## Known Issues (carried forward)

1. **EC2 image generation** — `generate_batch` gracefully returns failures because `google` SDK is absent on EC2. Generate images locally, then push `promo_proverbs.json` to EC2 via `sync_to_ec2.sh`.

2. **216 proverbs without composite_path** — Still need images before they can be scheduled. Run generate_batch locally with `limit=50` multiple times, then sync.

3. **GoWA webhook not configured** — `POST /api/promo/messages/inbound` is deployed and tested, but GoWA's outgoing webhook (for incoming messages) isn't pointed at it yet. Requires GoWA dashboard configuration.

4. **pCloud audio** — `audio_browse` returns empty on EC2 (pCloud not mounted). Use S3 URL overrides.

5. **EC2 `promo_settings.json` has empty `ai_providers: {}`** — falls back to DeepSeek, which works.

---

## What Phase 4 Should Focus On

**Priority 1: Local batch generation**
Run `POST /api/promo/broadcast_post/generate_batch` locally with large `limit` to fill composite_path for the remaining 216 proverbs. Then sync `promo_proverbs.json` to EC2 via `sync_to_ec2.sh`. Target: all 261 proverbs schedulable.

**Priority 2: GoWA webhook wiring**
Configure GoWA to send incoming messages to `http://13.218.60.13:5050/api/promo/messages/inbound`. Verify with a real WhatsApp test message from a known contact. Check that communication_log is updated on EC2.

**Priority 3: SLA automation**
Review `indaba-sla.md` active commitments and automate any that can be handled by the Discord bot (e.g. daily lead nudges, stale chapter alerts).

---

## SSH Access

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
```
