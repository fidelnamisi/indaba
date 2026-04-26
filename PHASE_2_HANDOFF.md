# Phase 2 Handoff — End-to-End Tool Testing + CRM Investigation
**Date:** 2026-04-26
**Session commit:** (see below — handoff only, no code changes)
**Phase:** 2 of 5 — Tool testing, CRM sync investigation, proverb image pipeline

---

## What Was Done

### 1. Pre-flight QA (Haiku agent)
All Phase 1 checks re-run and passed:
- All 3 services active (indaba-app, indaba-discord, indaba-sender)
- All 7 smoke-test routes returning expected HTTP codes
- Bot files fresh (modified 2026-04-26)
- Tool count: 26 (correct)
- All 9 Phase 1 functions confirmed in indaba_client.py
- Data: pipeline 82 entries (8 above baseline — benign), proverbs 258 ✓

### 2. End-to-end Discord Bot Tool Tests

All 6 tools tested via API (equivalent to Discord natural-language command):

| Tool | Command Simulated | Result |
|------|------------------|--------|
| `works_list_modules` | "Show me all chapters of Love Back" | ✅ PASS — 10 LB chapters returned |
| `scheduler_preview` | "Show next 14 days of scheduled content" | ✅ PASS — 5 items returned |
| `proverbs_create_batch` | "Create 3 African proverbs about perseverance" | ✅ PASS — 3 proverbs imported to EC2 |
| `flash_fiction_generate` | "300-word fantasy set in 1890s Lagos" | ✅ PASS — "The Price of Iron" (298w) |
| `crm_leads_summary` | "How many open leads do I have?" | ✅ PASS (after data fix — see below) |
| `scheduler_run` | "Fill the content schedule" (dry_run) | ✅ PASS — 5 items scheduled |

**Flash fiction generated (for reference):**
> "The Price of Iron" — Adunni, a Yoruba practitioner, is pressured by a colonial magistrate possessed by something ancient to sign herself into service in exchange for her brother's freedom. She accepts — having glimpsed his weakness in the shards of the cowrie shells she broke. 298 words. Genre: fantasy. Setting: Lagos, 1890s.

### 3. CRM Sync Investigation

**Findings:**

| Question | Answer |
|----------|--------|
| Does GoWA send inbound messages to Indaba? | **No.** No inbound webhook receiver exists. |
| What does `indaba-sender` store? | Only outbound message queue; no incoming message log. |
| Is there a pull route for inbound messages? | **No.** `/api/outbox/sync` only reconciles outbound status from EC2. |
| Where is `communication_log` updated? | Only for outbound (via `reconcile_promo_results`) or manual `log_communication` calls. |

**Root cause of `crm_leads_summary` returning 0 on EC2:**
EC2's `promo_leads.json` was empty — leads were only on local dashboard. Fixed by syncing file to EC2.

**Fix applied:**
```
scp promo_leads.json → ubuntu@13.218.60.13:/opt/indaba-app/data/promo_leads.json
```
Verified: `/api/promo/pipeline` now returns `total: 5` on EC2. ✓

**Gap for Phase 3:**
GoWA inbound message → lead `communication_log` pipeline does not exist. Building this requires:
1. A GoWA webhook receiver route in Indaba (or `indaba-sender`)
2. Logic to match the sender's phone number to a contact → lead
3. Append to `communication_log` as `direction: inbound`

### 4. Proverb Image Pipeline Test

| Step | Result |
|------|--------|
| `promo_broadcast_generate` on proverb `fbeb5774` | ✅ PASS — AI caption, meaning, image prompt, `composite_path` all set |
| `scheduler_run` (dry_run) picks up proverbs with `composite_path` | ✅ PASS — PROVERB slots in 14-day preview are filled |

**Note:** 208/258 local proverbs still lack `composite_path`. `promo_broadcast_generate` must be called on each before they can be scheduled. This is a batch job for Phase 3.

**Sample generated broadcast post:**
- Proverb: "With your hands you make your success, with your hands you destroy success."
- Caption: "You pour everything into building something beautiful. Love, a business, a dream. Then one careless word, one bitter silence, lets it slip through your fingers..."
- CTA: "React ❤️ if this is true for you."
- Image: Dark-skinned woman in Johannesburg apartment, cracked clay pot, indigo dusk light.

---

## EC2 Service Status (post-Phase 2)

| Service | Status | Port |
|---------|--------|------|
| `indaba-app` | ✅ active | 5050 |
| `indaba-discord` | ✅ active | — |
| `indaba-sender` | ✅ active | 5555 |

---

## Data State

| Store | EC2 count | Notes |
|-------|-----------|-------|
| Pipeline entries | 82 | 8 above Phase 1 baseline — benign |
| Proverbs | 261 | +3 perseverance proverbs added this session |
| Works | 10 | LB, OAO, ROTRQ, MOSAS, SAS, INDABA_PODCAST, BOOK_LAUNCH_2026, WRITERS_RETREAT_2026, TRAVELLER___R30, PATHFINDER |
| Leads | 5 | Synced from local this session (EC2 was 0) |

---

## Known Issues (carried forward)

1. **pCloud audio** — `audio_browse` returns empty on EC2 (pCloud not mounted). `audio_upload` will fail for local file lookup. Audio must use S3 URL overrides.

2. **EC2 `promo_settings.json` has empty `ai_providers: {}`** — falls back to DeepSeek, which works.

3. **`macos_contacts` route** — fails gracefully on EC2 (not a Mac). Not a blocker.

4. **208 proverbs without composite_path** — these cannot be scheduled until `promo_broadcast_generate` is run on each. No batch endpoint exists; must be called one-by-one or batched in Phase 3.

5. **GoWA inbound message sync gap** — incoming messages from leads are not captured anywhere. Requires Phase 3 webhook work.

6. **Data sync architecture** — local dashboard and EC2 are separate data stores. Changes made locally (leads, etc.) do not auto-sync to EC2. This was fixed manually for leads this session, but is a recurring risk.

---

## What Phase 3 Should Focus On

**Priority 1: Proverb batch image generation**
208 proverbs need images before they can be scheduled. Phase 3 should add:
- A batch `promo_broadcast_generate` endpoint (e.g. `POST /api/promo/broadcast_post/generate_batch?limit=20`)
- Or a Discord bot command: "Generate images for the next 20 proverbs"
- Then verify scheduler picks them up and `proverbs_remaining` increases

**Priority 2: GoWA inbound message capture**
Add a webhook endpoint to `indaba-sender` (or Indaba app) that:
1. Receives incoming GoWA messages
2. Looks up sender's phone in contacts
3. Appends to the matched lead's `communication_log` as `direction: inbound`
4. Returns 200 to GoWA

**Priority 3: Data sync hardening**
The local/EC2 data split is fragile. Options:
- Make EC2 the only data store and use SSH/VPN for local dev
- Add a `POST /api/sync/push` route that accepts a data file and writes it atomically
- Document which files should be edited only on EC2 vs locally

---

## SSH Access

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
```

EC2 IP: `13.218.60.13`
Key: `~/Indaba/ec2-key.pem`
