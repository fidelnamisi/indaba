# Indaba EC2 Infrastructure — Agent Handoff
**Last updated:** 2026-03-31
**Scope:** EC2 sender microservice, GoWA, SSH access, deployment workflow

---

## HOW TO USE THIS DOCUMENT

**To resume EC2 infrastructure work, run Claude Code from:**
```
cd ~/Indaba/indaba-ec2
claude
```

Claude Code reads `CLAUDE.md` (project instructions) and `indaba-sla.md` (SLA) on startup. This `HANDOFF-EC2.md` gives you the session context for the EC2 domain.

**Do not use this handoff for app-layer work** (Flask, UI, dashboard). That domain uses `~/Indaba/HANDOFF.md` and is run from `~/Indaba/`.

---

## 1. Architecture Summary

Indaba runs locally on Fidel's Mac (Flask, port 5050). EC2 handles all WhatsApp sending autonomously.

```
Indaba (local) → _mirror_to_cloud() → POST /queue → EC2 Sender (port 5555) → GoWA (port 3000) → WhatsApp
```

EC2 cron now fires **every minute** (changed 2026-03-31 from 3x/day) and calls `POST /api/promo/sender/pop_next` to dispatch the next due message.

---

## 2. EC2 Details

- **Instance ID:** `i-0b381c5c13988ca76`
- **Public IP:** `13.218.60.13`
- **Region:** us-east-1
- **GoWA container:** `gowa_gowa_1`, port 3000, docker-compose at `/opt/gowa/docker-compose.yml`
- **Sender service:** `/opt/indaba-sender/sender.py`, port 5555, systemd `indaba-sender`
- **Queue file:** `/opt/indaba-sender/data/queue.json`
- **EC2 cron:** `/etc/cron.d/indaba-sender`
- **S3 bucket for images:** `indaba-media-fidel`
- **Status dashboard:** `http://13.218.60.13:5555/status` (Basic Auth: admin / admin)
- **Master copy of sender.py:** `/Users/fidelnamisi/Indaba/tmp/sender.py` — always edit this, then deploy to EC2

---

## 3. SSH Access — How It Works

There is NO permanent SSH key in authorized_keys. Every session requires EC2 Instance Connect.

**All-in-one deploy snippet (copy-paste):**
```bash
# Step 1: Restore key
cp /Users/fidelnamisi/Indaba/ec2-key.pem /tmp/ec2-temp-key
chmod 600 /tmp/ec2-temp-key

# Step 2: Push public key and SSH immediately (must happen within 60s)
PUB=$(ssh-keygen -y -f /tmp/ec2-temp-key)
aws ec2-instance-connect send-ssh-public-key \
  --instance-id i-0b381c5c13988ca76 \
  --instance-os-user ubuntu \
  --ssh-public-key "$PUB" \
  --region us-east-1 > /dev/null && \
ssh -i /tmp/ec2-temp-key -o StrictHostKeyChecking=no ubuntu@13.218.60.13 "your command here"
```

**Critical:** The 60-second window starts when `send-ssh-public-key` completes. Always chain `send-ssh-public-key` and `ssh`/`scp` in a single shell command with `&&`. Never run them as separate Bash tool calls.

**To make the SSH key permanent** (eliminates Instance Connect dance permanently):
```bash
PUB=$(ssh-keygen -y -f /tmp/ec2-temp-key)
aws ec2-instance-connect send-ssh-public-key \
  --instance-id i-0b381c5c13988ca76 \
  --instance-os-user ubuntu \
  --ssh-public-key "$PUB" \
  --region us-east-1 > /dev/null && \
ssh -i /tmp/ec2-temp-key -o StrictHostKeyChecking=no ubuntu@13.218.60.13 \
  "echo '$PUB' >> ~/.ssh/authorized_keys"
```

---

## 4. Deploying sender.py Changes

Master copy: `/Users/fidelnamisi/Indaba/tmp/sender.py`

Always edit the master copy first, then deploy:
```bash
cp /Users/fidelnamisi/Indaba/ec2-key.pem /tmp/ec2-temp-key && chmod 600 /tmp/ec2-temp-key
PUB=$(ssh-keygen -y -f /tmp/ec2-temp-key)
aws ec2-instance-connect send-ssh-public-key \
  --instance-id i-0b381c5c13988ca76 \
  --instance-os-user ubuntu \
  --ssh-public-key "$PUB" \
  --region us-east-1 > /dev/null && \
scp -i /tmp/ec2-temp-key -o StrictHostKeyChecking=no \
  /Users/fidelnamisi/Indaba/tmp/sender.py \
  ubuntu@13.218.60.13:/tmp/sender_new.py && \
ssh -i /tmp/ec2-temp-key -o StrictHostKeyChecking=no ubuntu@13.218.60.13 \
  "sudo cp /tmp/sender_new.py /opt/indaba-sender/sender.py && \
   sudo systemctl restart indaba-sender && sleep 2 && \
   curl -s http://localhost:5555/health"
```

---

## 5. Sender Endpoints

All require Basic Auth `admin:admin` except `/health`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | `{ok, queued, gowa_device}` — no auth needed |
| GET | `/status` | HTML dashboard |
| GET | `/queue` | Full queue as JSON |
| POST | `/queue` | Enqueue a message |
| PUT | `/queue/<id>` | Update `content`, `scheduled_at`, `recipient_phone`, `recipient_name` of a queued message |
| POST | `/queue/<id>/send_now` | Send immediately |
| POST | `/queue/<id>/preview` | Send to +27822909093 only, stays queued |
| POST | `/queue/<id>/delete` | Remove single message |
| POST | `/queue/delete-sent` | Remove ALL sent messages |
| POST | `/queue/delete-failed` | Remove ALL failed messages |
| POST | `/api/promo/sender/pop_next` | Cron entry point — sends next due message |

---

## 6. Status Dashboard Features (as of 2026-03-31)

`http://13.218.60.13:5555/status`

- **Sortable columns** — click any bold column header to toggle asc/desc (▲/▼). Defaults to Scheduled ascending on load.
- **Date format** — all times shown as `Tue 31 Mar 14:05` SAST (GMT+2).
- **Bulk delete buttons** — "Delete all sent (N)" and "Delete all failed (N)" above the table, disabled when count is 0.
- **Edit time button** (purple) — per queued/failed row. Opens a modal with a SAST datetime picker pre-filled with current scheduled time. Save converts to UTC and calls `PUT /queue/<id>`. Auto-refresh pauses while the modal is open.
- **Auto-refresh** — every 2 minutes (JS-based, pauses when Edit time modal is open).
- **Individual row actions** — Send now (amber), Preview (blue), Delete (red) — queued and failed only.

---

## 7. Cron Schedule

**File:** `/etc/cron.d/indaba-sender`

**Current config (every minute):**
```
* * * * * root curl -s -X POST http://localhost:5555/api/promo/sender/pop_next -u admin:admin -H "Content-Type: application/json" >> /var/log/indaba-cron.log 2>&1
```

**Cron log:** `/var/log/indaba-cron.log` — each line is the JSON response from `pop_next`. Useful for confirming sends.

**`pop_next` behaviour:** Sends the single next-due queued message (`scheduled_at <= now`). FIFO (no scheduled_at) messages are sent after all timed messages. Sends one message per call — if multiple are due simultaneously, each subsequent one fires on the next cron tick (next minute).

---

## 8. GoWA Device ID — Self-Healing

GoWA's device UUID changes on every new WhatsApp QR scan. `get_device_id()` in `sender.py` **parses Docker logs dynamically** — no redeploy needed after rescanning.

If Preview/Send fails with "device not found":
1. Open `http://13.218.60.13:3000`
2. Scan QR code with WhatsApp (Linked Devices → Link a Device)
3. Done — sender auto-discovers new UUID

**Why it disconnects:** REMOTE_LOGOUT events trigger when Fidel's phone removes the linked device from WhatsApp → Linked Devices. After reconnecting, leave that device alone on his phone.

---

## 9. WA Channel Phone Format

**Correct JID:** `120363422545873811@newsletter`

This is the real WhatsApp newsletter channel JID for Fidel's "Wisdom and Love Stories" channel. All messages sent to the channel MUST use this exact string as `recipient_phone`.

**Bug history:** An older code path in `routes/works.py` used a hardcoded fallback `'WA-CHANNEL'`. This was fixed 2026-03-31 — `routes/works.py` now reads `channel_id` from `promo_settings.json`. No action needed on EC2 for new messages. The two affected queue entries were already corrected in place on EC2.

**GoWA channel sending:** GoWA v8.3.0 supports sending to newsletter JIDs via both `/send/message` and `/send/image` endpoints — the same endpoints used for regular phone numbers. The `@newsletter` suffix in the JID is what GoWA uses to route correctly.

---

## 10. Indaba `app.py` — EC2-Related Code

Two functions in `app.py` handle cloud mirroring (called from `_add_to_universal_queue()`):

- `_upload_image_to_s3(local_path)` — uploads local image to S3, returns public URL
- `_mirror_to_cloud(msg)` — POSTs message to EC2 `/queue`; if message has a local image path, uploads to S3 first

Both are silent no-ops if `EC2_SENDER_URL` env var is not set.

---

## 11. Pending Tasks

- [ ] **Make SSH key permanent** — run the command in Section 3 once while you have access, so future sessions skip Instance Connect entirely.

- [ ] **Create two Cowork scheduled tasks** (must be done from a fresh non-task Cowork session):
  - `indaba-content-generation`: 7am SAST daily — hits `POST http://localhost:5050/api/promo/wa_post/bulk_generate {"count": 3}`, writes alert if Indaba is offline
  - `indaba-approval-reminder`: 12pm SAST daily — checks EC2 `/health`, if `queued == 0` sends WhatsApp nudge to `27822909093` via EC2 sender

- [ ] **Install LaunchAgent** for Indaba auto-start (Fidel runs from `~`):
  ```
  cp ~/Indaba/com.fidel.indaba.plist ~/Library/LaunchAgents/
  launchctl load ~/Library/LaunchAgents/com.fidel.indaba.plist
  ```

- [ ] **Add env vars to `~/.zshrc`** if not already present:
  ```
  export EC2_SENDER_URL=http://13.218.60.13:5555
  export AWS_DEFAULT_REGION=us-east-1
  export INDABA_S3_BUCKET=indaba-media-fidel
  ```

---

## 12. Architecture Rules (Non-Negotiable)

1. **Master copy first** — always edit `/Users/fidelnamisi/Indaba/tmp/sender.py`, then deploy. Never edit `/opt/indaba-sender/sender.py` directly on EC2.
2. **SSH key window** — `send-ssh-public-key` and the subsequent `ssh`/`scp` must be in a single chained command. The 60-second window expires fast.
3. **Atomic queue writes** — `save_queue()` uses `os.replace()`. Never write queue.json directly.
4. **Do not cross domains** — this agent handles EC2/sender only. App-layer work (Flask, UI) belongs in `~/Indaba/` with `HANDOFF.md`.
