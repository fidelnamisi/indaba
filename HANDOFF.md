# Indaba Handoff Log

---

## 2026-04-27 — Discord Bot Live + Phase 6 Design

### What Changed

**Discord bot is now live on EC2.** Tokens were configured, bot connects to Discord and responds in `#indaba-ops`.

**Fixes applied this session:**
- SAST (GMT+2) timezone in `roadmap.py` — `!idea` timestamps now show local time
- `discord_bot/indaba-discord.service` added to `.gitignore` — tokens can never be accidentally committed
- `!preview`, `!generate [id]`, `!queue <id>` commands added (then superseded — see below)

**Decision: Scrap explicit commands for content operations.**

Fidel wants natural language all the way. Explicit commands like `!generate` and `!queue <id>` are confusing (e.g. `!generate` sounds generic but was proverb-only). The next session will replace them with a conversational agent that previews write operations before executing them.

**Next session goal:** See `PHASE_6_HANDOFF.md` for full spec.

### EC2 Deployment

Bot is live. To pull updates after code changes:
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
cd /opt/indaba-discord && git pull && sudo systemctl restart indaba-discord
```

---

## 2026-04-21 — EC2 Queue: Reschedule + Bulk Delete

### What Changed

Two UX improvements to the EC2 Sender status dashboard (`http://13.218.60.13:5555/status`):

**1. Reschedule (inline edit)**
Clicking the scheduled time cell on any queued/failed row now reveals an inline datetime picker (pre-filled with current SAST time). Save converts back to UTC and calls `PUT /queue/<id>`. Cancel reverts to display mode. FIFO (unscheduled) rows also support this — clicking "FIFO" opens the picker so a schedule can be set.

**2. Bulk delete via checkboxes**
A checkbox column is now the leftmost column of the table. Checkboxes appear only for queued/failed rows. A "Select all" checkbox sits in the header. When one or more rows are checked, a red "Delete selected (N)" button appears above the table. Clicking it calls the new `POST /queue/bulk-delete` endpoint with the selected IDs.

**New endpoint:**
`POST /queue/bulk-delete` — accepts a JSON array of message IDs, removes them all from `queue.json` in one operation.

### Files Changed

| File | Change |
|------|--------|
| `indaba-ec2/tmp/sender.py` | Added `POST /queue/bulk-delete` endpoint; rewrote `status_page()` with checkbox column, inline reschedule widget, and bulk delete bar |

### Deployed
Deployed to EC2 via SCP + `systemctl restart indaba-sender`. Health check confirmed 6 queued messages intact.

---

## 2026-04-21 — Live EC2 Queue as Scheduling Source of Truth

### Problem

When new proverbs were scheduled (bulk approve or single queue), the scheduler read `promo_messages.json` to determine which time slots were already occupied. If messages had been manually deleted from EC2 — or had failed and been removed — those deletions were never reflected locally. The scheduler treated the deleted slots as still occupied and pushed new proverbs further into the future than intended.

### Root Cause

`bulk_approve_broadcast_posts()` and `queue_broadcast_proverb()` both seeded `existing_queue` from the local `promo_messages.json` file. That file is a write-once mirror — Indaba pushes to it when queuing but never pulls from EC2 to reconcile deletions, failures, or manual removals. Local state could silently diverge from actual EC2 queue state.

### Fix Applied

**1. `services/distribution_service.py` — `fetch_ec2_queue()`**

New function that calls `GET /queue` on EC2 Sender (which returns the full `queue.json` array), filters to `status == "queued"`, and returns the live list. Returns `None` on any failure (EC2 unreachable, timeout, etc.).

**2. `routes/promo_broadcast_post.py` — `bulk_approve_broadcast_posts()`**

`acc_queue` now seeds from `fetch_ec2_queue()` instead of local `promo_messages.json`. Falls back to local file if EC2 is unreachable. Response includes `"schedule_source": "ec2_live"` or `"local_fallback"` so divergence is visible.

**3. `routes/promo_broadcast_post.py` — `queue_broadcast_proverb()`**

Same fix for the single-proverb queue endpoint.

### Invariant

The scheduler now always reflects actual EC2 queue state when computing the next available slot. Manual deletions, failed-message cleanup, or any EC2-side changes are automatically accounted for at schedule time — no reconciliation step needed.

### Key Learnings

- `promo_messages.json` is a **write-only history log**, not a reliable queue mirror. Never use it as scheduling input.
- The EC2 Sender's `GET /queue` endpoint (added in the original EC2 deployment) returns the complete live queue — use it as the authority.
- The fallback to local is intentional: if EC2 is down, scheduling still works, but `schedule_source: "local_fallback"` in the response flags the degraded state.

### Files Changed

| File | Change |
|------|--------|
| `services/distribution_service.py` | Added `fetch_ec2_queue()` — fetches live EC2 queue |
| `routes/promo_broadcast_post.py` | `bulk_approve` and `queue_broadcast_proverb` now use live EC2 queue for scheduling |

---

## 2026-04-21 — S3 Image URL Expiry Fix (Proverb / WA broadcasts)

### Problem

All queued proverb broadcasts were failing on EC2 with:
```
failed to download image from URL — HTTP request failed with status: 403 Forbidden
```

### Root Cause

When proverb messages are queued, their images are uploaded to S3 and a **pre-signed URL** is stored in the EC2 queue. AWS S3 pre-signed URLs have a hard 7-day maximum expiry when using IAM roles. Proverbs queued on Apr 9 and Apr 13 (8–12 days earlier) had expired URLs. GoWA received the expired URL, tried to download the image, and got 403.

### Fix Applied

**1. S3 bucket policy** — Set a permanent public read policy on the `images/*` prefix of the `indaba-media-fidel` bucket. Any object uploaded under that prefix is now publicly readable forever.

**2. Code change** (`services/distribution_service.py`, `_upload_image_to_s3`) — Removed pre-signed URL generation. Now returns a permanent public URL:
```python
# Before (broke after 7 days)
presigned_url = s3.generate_presigned_url('get_object', ..., ExpiresIn=604800)

# After (permanent)
public_url = f"https://{bucket}.s3.amazonaws.com/{key}"
```

**3. Immediate repair** — Re-uploaded all 20 stuck proverb images to S3 and updated the EC2 queue entries with fresh permanent URLs. 19/20 updated successfully; 1 was already absent from the EC2 queue (likely already processed).

### Key Learnings

- **Never use pre-signed S3 URLs for queued media.** Proverbs are queued days or weeks ahead — any expiry window shorter than the queue depth will cause silent breakage.
- **The fix is permanent.** `images/*` in the S3 bucket is now publicly readable. All future proverb/broadcast images uploaded there will work forever.
- **The bucket** (`indaba-media-fidel`) has all public access blocks disabled — public bucket policies are supported.
- If the bucket ever needs to restrict public access again, the alternative is to store images on EC2 itself and serve from there (EC2 is always reachable by GoWA on the same host).

### Files Changed

| File | Change |
|------|--------|
| `services/distribution_service.py` | `_upload_image_to_s3` — replaced pre-signed URL with permanent public URL |

---

## 2026-04-19 — Discord Bot + EC2 Indaba Deployment

### What was built

**Indaba Bot** — a Discord bot that lets you operate Indaba from any Discord channel, 24/7, even when your Mac is off.

---

### Architecture

```
Discord (your phone / any device)
        │
        ▼
Indaba Bot (EC2 /opt/indaba-discord, port — none, systemd service: indaba-discord)
        │
        ├──► Indaba Flask API (EC2 /opt/indaba-app:5050, systemd service: indaba-app)
        │         └── data/ seeded from Mac on 2026-04-19 (74 pipeline entries)
        │
        └──► EC2 Sender health (localhost:5555)
```

The Mac stays your **development** instance. EC2 is the **ops** instance. They share the same GitHub repo but have independent data directories. When the Mac modifies data, push to GitHub and re-seed EC2 if needed.

---

### Activating the Bot — One-Time Setup Required

The bot code is deployed and ready. You just need a Discord token:

**Step 1 — Create the Discord Application**
1. Go to https://discord.com/developers/applications
2. Click "New Application" → name it "Indaba Bot"
3. Go to "Bot" tab → click "Add Bot"
4. Under "Privileged Gateway Intents" enable **Message Content Intent**
5. Copy the **Bot Token**

**Step 2 — Invite the Bot to your Server**
1. Go to "OAuth2" → "URL Generator"
2. Scopes: `bot`
3. Bot Permissions: `Send Messages`, `Read Message History`, `View Channels`
4. Copy the URL and open it → select your server

**Step 3 — Create the #indaba-ops channel** in your Discord server

**Step 4 — Add the token to EC2**
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
sudo nano /etc/systemd/system/indaba-discord.service
# Replace: DISCORD_BOT_TOKEN=PASTE_TOKEN_HERE
# With:    DISCORD_BOT_TOKEN=your_actual_token
sudo systemctl daemon-reload
sudo systemctl start indaba-discord
sudo systemctl status indaba-discord
```

**Step 5 — (Optional) Enable GitHub push from bot's `!idea` command**
```bash
# Create a GitHub Personal Access Token with repo scope at github.com/settings/tokens
sudo nano /etc/systemd/system/indaba-discord.service
# Set GITHUB_TOKEN=your_github_pat
sudo systemctl daemon-reload && sudo systemctl restart indaba-discord
```

---

### Bot Commands

| Command | What it does |
|---------|-------------|
| `!hub` | Pipeline overview (producing/publishing/promoting counts) |
| `!pipeline [book] [stage]` | List pipeline entries, optionally filtered |
| `!entry <id>` | Get details on one pipeline entry |
| `!stage <id> <stage>` | Move entry to producing\|publishing\|promoting |
| `!publish <id>` | Publish chapter to realmsandroads.com |
| `!deploy` | Deploy website to AWS Amplify |
| `!deploystatus` | Check deploy status |
| `!sync <work_code>` | Compare pipeline vs live website |
| `!works` | List all book series |
| `!status` | EC2 sender health |
| `!idea <text>` | Capture idea → ROADMAP.md → GitHub |
| `!help` | Full command list |

Natural language also works — any message not starting with `!` is parsed by Claude Haiku.

**Book codes:** LB, OAO, ROTRQ, MOSAS  
**Stages:** producing, publishing, promoting

---

### EC2 Services Summary

| Service | Location | Port | Status |
|---------|----------|------|--------|
| `indaba-app` | `/opt/indaba-app` | 5050 | ✅ running |
| `indaba-discord` | `/opt/indaba-discord` | — | ⏸ waiting for DISCORD_BOT_TOKEN |
| `indaba-sender` | `/opt/indaba-sender` | 5555 | ✅ running (existing) |

Check all services: `sudo systemctl status indaba-app indaba-discord indaba-sender`

---

### Files Added

| File | Purpose |
|------|---------|
| `discord_bot/bot.py` | Main Discord bot |
| `discord_bot/indaba_client.py` | HTTP wrapper for Indaba API |
| `discord_bot/claude_agent.py` | Claude Haiku NLP parser |
| `discord_bot/roadmap.py` | ROADMAP.md idea capture + git push |
| `discord_bot/config.py` | Env var configuration |
| `discord_bot/indaba-app.service` | Systemd service for EC2 Indaba |
| `discord_bot/indaba-discord.service` | Systemd service for Discord bot |
| `ROADMAP.md` | Idea capture file — appended by `!idea` |

---

### Data Sync (Mac ↔ EC2)

Data lives in `data/` which is gitignored. Current approach:
- Mac is dev, EC2 is ops — they may diverge over time
- To push Mac data to EC2: `rsync -av --include='*.json' --exclude='*' data/ ubuntu@13.218.60.13:/opt/indaba-app/data/` (using the permanent key installed today)
- To pull EC2 data to Mac: reverse the above
- SSH key is now **permanent** — no more 60-second EC2 Instance Connect dance

---

### SSH Access (Updated)

The EC2 SSH key is now permanent. Direct SSH works without Instance Connect:
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
```

No more `aws ec2-instance-connect send-ssh-public-key` needed.

---

## 2026-04-17 — Chapter HTML Template Bug Fixes

**File:** `services/chapter_html_template.py`

### Bug 1 — Wrong callout class (`patreon-callout` → `support-callout`) ✅ FIXED

**What happened:** The chapter template rendered a `<div class="patreon-callout">` block with a hardcoded Patreon link.

**Why it was wrong:** `main.js` on realmsandroads.com looks for `.support-callout` and replaces its content dynamically based on the reader's membership tier. With the wrong class, JS never fired and readers saw a hardcoded Patreon link instead of the correct membership CTA.

**Fix applied:** Replaced the block with:
```html
<div class="support-callout">
  <h3>Enjoying the story?</h3>
  <p>Support the creation of more stories — become a member and get early access to new chapters.</p>
  <a href="/subscribe.html" class="btn btn-primary">Join Today ›</a>
</div>
```

**Rule:** Never use `.patreon-callout` or reference `patreon.com` in any chapter template.

---

### Bug 2 — Unstripped markdown in chapter body ✅ FIXED

**What happened:** Content fields containing standalone markdown bold lines (e.g. `**Glass Hearts**`) were passed verbatim into `<p>` tags. The site has no markdown renderer, so asterisks were displayed raw to readers.

**Fix applied:** `prose_to_html()` now skips any paragraph that is a standalone markdown bold/italic line (regex: `^\*{1,3}.+\*{1,3}$`). These lines are chapter title echoes — the title is already rendered in the `<h1>` above the article.

**Broader rule:** Content arriving at the publish endpoint should be plain prose. Any standalone `**title**` lines at the top of a content field are dropped before HTML rendering.
