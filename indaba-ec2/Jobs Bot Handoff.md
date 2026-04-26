# Jobs Bot Handoff

**Created:** 2026-04-22  
**Last updated:** 2026-04-22 — system completed and live  
**Author:** Fidel + Claude  
**Scope:** Incoming WhatsApp channel message monitoring → AI job matching pipeline

---

## Status: LIVE

Pipeline is fully operational as of 2026-04-22. No localtunnel. No manual steps. Runs autonomously on EC2.

```
WhatsApp Jobs Channel (120363187142771346@newsletter)
        ↓
   GoWA (port 3000, Docker)
        ↓  POST http://host.docker.internal:3001/webhook
indaba-jobs-webhook (port 3001) — filters to jobs channel only
        ↓  POST {"text": "..."} → http://localhost:5555/jobwebhook
indaba-sender /jobwebhook — calls Deepseek, scores 1-10
        ↓  score >= 7
   WA DM sent immediately to +27822909093
```

**Jobs channel JID confirmed:** `120363187142771346@newsletter`  
**Evaluation model:** Deepseek (`deepseek-chat`) via `/jobwebhook` on indaba-sender  
**Threshold:** score ≥ 7/10 → WA DM alert. Below 7 → logged only.

---

## What This Does

GoWA (the WhatsApp gateway running on EC2) receives messages from all WhatsApp channels (newsletters) that Fidel follows. A lightweight Python service (`indaba-jobs-webhook`) filters those messages, keeps only ones from the confirmed jobs channel, and forwards the text body to `indaba-sender`'s `/jobwebhook` endpoint. That endpoint calls Deepseek to evaluate fit for Fidel (professional African fantasy fiction author). If the score is 7 or higher, it sends an instant WhatsApp DM to Fidel's phone.

---

## Infrastructure at a Glance

| Component | Location | Port | Managed by |
|---|---|---|---|
| GoWA | EC2, Docker container `gowa_gowa_1` | 3000 | `docker-compose` at `/opt/gowa/docker-compose.yml` |
| indaba-jobs-webhook | EC2, `/opt/indaba-jobs-webhook/webhook.py` | 3001 | systemd `indaba-jobs-webhook` |
| indaba-sender | EC2, `/opt/indaba-sender/sender.py` | 5555 | systemd `indaba-sender` |
| AI job matcher | **Built into indaba-sender `/jobwebhook`** | 5555 | part of indaba-sender |

**EC2 details:**
- Instance ID: `i-0b381c5c13988ca76`
- Public IP: `13.218.60.13`
- Region: `us-east-1`
- SSH key: `~/Indaba/ec2-key.pem` (use Instance Connect — see SSH section)

**Master source file (edit locally, deploy to EC2):**
`~/Indaba/indaba-ec2/tmp/sender.py` — for indaba-sender  
`~/Indaba/indaba-ec2/Jobs Bot Handoff.md` — this file

The `indaba-jobs-webhook/webhook.py` lives only on EC2 at `/opt/indaba-jobs-webhook/webhook.py`. If you need to edit it, pull it down first.

---

## GoWA Webhook Configuration

GoWA is configured to fire webhooks to **two** targets simultaneously:

```yaml
# /opt/gowa/docker-compose.yml
command: >
  rest
  --webhook="http://host.docker.internal:5555/gowa/webhook"
  --webhook="http://host.docker.internal:3001/webhook"
  --webhook-events="message"
  --webhook-secret="indaba-wa-secret"
```

- Port **5555** is the existing `indaba-sender` (handles outbound queue, inbound DMs for CRM)
- Port **3001** is the new `indaba-jobs-webhook` (handles newsletter channel monitoring)

Both run independently. If one fails, GoWA logs the failure and continues to the other.

---

## GoWA v8.3.0 Breaking Changes (Critical Knowledge)

**This is the most important section.** GoWA v8.3.0 changed its webhook format completely from older versions. If you upgrade GoWA or restore from an older backup, this will break again.

### Authentication
| Version | Header sent by GoWA | How to verify |
|---|---|---|
| Pre-v8.3 | `X-Webhook-Secret: <plain string>` | Simple string comparison |
| **v8.3+** | `X-Hub-Signature-256: sha256=<hmac>` | HMAC-SHA256 signature |

**Current fix:** Both services (port 3001 and port 5555) have secret checking **disabled** because both ports are only reachable via `host.docker.internal` from inside the GoWA Docker container — they are not exposed to the internet. This is safe.

### Payload Format
| Version | Structure |
|---|---|
| Pre-v8.3 | `{"code": "message", "results": {"from": "...", "message": {"conversation": "..."}, ...}}` |
| **v8.3+** | `{"device_id": "...", "event": "message", "payload": {"body": "...", "chat_id": "...", "from": "...", ...}}` |

**Key field mappings (v8.3+):**
- Event type: `payload["event"]` (was `payload["code"]`)
- Message sender: `payload["payload"]["chat_id"]` (was `payload["results"]["from"]`)
- Message text: `payload["payload"]["body"]` (was `payload["results"]["message"]["conversation"]`)
- Is outbound: `payload["payload"]["is_from_me"]`
- Sender name: `payload["payload"]["from_name"]`

**Newsletter messages** have `chat_id` ending in `@newsletter`.  
**Group messages** have `chat_id` ending in `@g.us`.  
**Direct messages** have `chat_id` ending in `@s.whatsapp.net`.

---

## indaba-jobs-webhook Service

### Files on EC2
```
/opt/indaba-jobs-webhook/
├── webhook.py                          # Main service
├── logs/
│   ├── webhook.log                     # Structured log (INFO/WARNING/ERROR)
│   └── raw_events.jsonl                # Full raw payloads (one JSON per line)
/etc/systemd/system/indaba-jobs-webhook.service      # Service definition
/etc/systemd/system/indaba-jobs-webhook.service.d/
└── override.conf                       # Env var overrides (DESTINATION_URL etc.)
```

### Environment Variables
Set in `/etc/systemd/system/indaba-jobs-webhook.service.d/override.conf`:

| Variable | Current value | Purpose |
|---|---|---|
| `DESTINATION_URL` | `http://localhost:5555/jobwebhook` | Indaba sender job evaluator (permanent, no tunnel) |
| `WEBHOOK_SECRET` | *(empty)* | Disabled — internal service only |
| `PORT` | `3001` | Listen port |
| `LOG_DIR` | `/opt/indaba-jobs-webhook/logs` | Log directory |
| `TARGET_CHANNEL_JID` | `120363187142771346@newsletter` | Jobs newsletter channel (confirmed 2026-04-22) |

**To change DESTINATION_URL or set TARGET_CHANNEL_JID:**
```bash
sudo systemctl edit indaba-jobs-webhook
# Add/update under [Service]:
# Environment="DESTINATION_URL=https://your-new-url/jobwebhook"
# Environment="TARGET_CHANNEL_JID=120363XXXXXXXXX@newsletter"
sudo systemctl restart indaba-jobs-webhook
```

### What the service does
1. Receives POST from GoWA at `/webhook`
2. Checks `event == "message"` — skips all other event types
3. Checks `payload.chat_id` ends in `@newsletter` — skips DMs and groups
4. If `TARGET_CHANNEL_JID` is set, skips channels that don't match it exactly
5. Extracts `payload.body` as the message text
6. POSTs `{"text": "<message body>"}` to `DESTINATION_URL`
7. Logs everything

---

## Subscribed WhatsApp Channels (23 total)

GoWA does not have an API to list channel names. Names are not stored in the local SQLite DB. The JIDs are:

```
120363164785255389@newsletter
120363165733441808@newsletter
120363169665563557@newsletter
120363172718569443@newsletter
120363177984810951@newsletter
120363181386696782@newsletter
120363185850687173@newsletter
120363187142771346@newsletter
120363222465301774@newsletter
120363225230285905@newsletter
120363238285031857@newsletter
120363271527826145@newsletter
120363301950734804@newsletter
120363316802050587@newsletter
120363332971213846@newsletter
120363338873616763@newsletter
120363389447463284@newsletter
120363402690237931@newsletter
120363403036573598@newsletter
120363404237301954@newsletter
120363405343216888@newsletter
120363419831551186@newsletter
120363424138390974@newsletter
```

**To identify which JID is the jobs channel:** wait for a post from that channel, then check:
```bash
# SSH in first (see SSH section), then:
grep "Channel msg" /opt/indaba-jobs-webhook/logs/webhook.log
```
The log line shows: `Channel msg from 120363XXXXXXXXX@newsletter (Channel Name): message text...`

---

## Monitoring Commands

### Watch the live log (from your Mac terminal)
A script is saved at `~/Indaba/indaba-ec2/watch-jobs-log.sh`. Run it from any folder:
```bash
~/Indaba/indaba-ec2/watch-jobs-log.sh
```
Ctrl+C to exit.

**Why a script and not a raw command:** The AWS Instance Connect command is long and breaks across lines when pasted into zsh, causing `--ssh-public-key` to be interpreted as a separate command and failing with a ParamValidation error. Always use the script.

### Check service status (once SSHed in)
```bash
sudo systemctl status indaba-jobs-webhook
sudo systemctl status indaba-sender
sudo docker ps | grep gowa
```

### Health checks
```bash
curl http://localhost:3001/health        # jobs-webhook
curl http://localhost:5555/health        # indaba-sender
curl -u admin:admin http://localhost:3000/devices   # GoWA device status
```

### Send a test message through the full pipeline
```bash
curl -s -X POST http://localhost:3001/webhook \
  -H 'Content-Type: application/json' \
  -d '{
    "device_id": "27822909093@s.whatsapp.net",
    "event": "message",
    "payload": {
      "body": "Test job post: Senior Developer needed",
      "chat_id": "120363271527826145@newsletter",
      "from": "0@s.whatsapp.net",
      "from_name": "Test Channel",
      "id": "TESTID",
      "is_from_me": false,
      "timestamp": "2026-04-22T00:00:00Z"
    }
  }'
```
Expected response: `{"destination_status": 200, "forwarded": true, "ok": true}`  
If DESTINATION_URL is unreachable you'll get a non-200 `destination_status` or a 502.

---

## SSH Access

No permanent key in `authorized_keys`. Uses EC2 Instance Connect (60-second window).

```bash
cp ~/Indaba/ec2-key.pem /tmp/ec2-temp-key && chmod 600 /tmp/ec2-temp-key
PUB=$(ssh-keygen -y -f /tmp/ec2-temp-key)
aws ec2-instance-connect send-ssh-public-key \
  --instance-id i-0b381c5c13988ca76 \
  --instance-os-user ubuntu \
  --ssh-public-key "$PUB" \
  --region us-east-1 > /dev/null && \
ssh -i /tmp/ec2-temp-key -o StrictHostKeyChecking=no ubuntu@13.218.60.13
```

**Rule:** `send-ssh-public-key` and the `ssh` command must be chained with `&&` in one shell command. If you run them separately, the 60-second window will expire before you connect.

---

## Diagnosing Common Failures

### "forwarded: false, reason: DESTINATION_URL not set"
DESTINATION_URL env var is empty. Check the override.conf:
```bash
sudo cat /etc/systemd/system/indaba-jobs-webhook.service.d/override.conf
```
Fix: add/update `Environment="DESTINATION_URL=https://..."` and restart.

### "destination_status: 408" or "destination_status: 5xx"
The jobs-webhook reached DESTINATION_URL but got an error back. The webhook receiver side is working. The problem is with the AI endpoint:
- 408 = request timeout (AI server slow to respond, or localtunnel cold start)
- 502/503 = AI server down
- 404 = wrong path in DESTINATION_URL

Check if the AI endpoint is running locally and the tunnel is active.

### "destination_status: 200 but nothing happens"
The full pipeline is working. The issue is inside the AI job-matching service itself.

### GoWA logs show "webhook returned status 403" on both targets
This was the original bug. It means GoWA is sending `X-Hub-Signature-256` HMAC auth (v8.3.0+) but the services are checking for the old `X-Webhook-Secret` header.

Fix: ensure both services have secret checking disabled (empty `WEBHOOK_SECRET`):
```bash
sudo cat /etc/systemd/system/indaba-jobs-webhook.service.d/override.conf
# Should contain: Environment="WEBHOOK_SECRET="
```
For indaba-sender, the secret check is removed from the code (no env var needed).

### GoWA logs show "webhook returned status 403" only on port 5555
The `indaba-sender` reverted to an old version with the plain-secret check. Re-deploy the current `indaba-ec2/tmp/sender.py`.

### Service won't start — "Address already in use" on port 3001
A stale process is holding the port (e.g. leftover `nc` from debugging):
```bash
sudo fuser -k 3001/tcp
sudo systemctl start indaba-jobs-webhook
```

### GoWA container is down
```bash
cd /opt/gowa && sudo docker-compose up -d
```
After restart, GoWA auto-reconnects the WhatsApp session. Check:
```bash
curl -u admin:admin http://localhost:3000/devices
# Should show: "state": "logged_in"
```
If state is NOT `logged_in`, open `http://13.218.60.13:3000` in a browser and scan QR.

### GoWA is up but not firing webhooks at all
Check the GoWA startup args include both webhook targets:
```bash
sudo docker inspect gowa_gowa_1 --format '{{range .Args}}{{.}} {{end}}'
```
Should show both `--webhook=http://host.docker.internal:5555/...` and `--webhook=http://host.docker.internal:3001/...`.

If a `--webhook` is missing, the docker-compose.yml was overwritten. Restore it:
```bash
sudo cat /opt/gowa/docker-compose.yml
# If missing the 3001 line, edit and add it back, then:
cd /opt/gowa && sudo docker-compose down && sudo docker-compose up -d
```

### Webhook receiver is running but skipping real channel messages
Check `TARGET_CHANNEL_JID` — if it's set to the wrong JID it will skip everything:
```bash
sudo systemctl show indaba-jobs-webhook -p Environment
```
To accept all newsletter channels temporarily, set `TARGET_CHANNEL_JID=` (empty) and restart.

### "No text body" logged for channel messages
The channel sent an image-only post (no caption). The `payload.body` field will be absent. Currently the service skips image-only posts. This is by design — the AI matcher needs text.

---

## New Endpoints on indaba-sender (added 2026-04-22)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/jobwebhook` | none | Receive job text, evaluate with Deepseek, DM Fidel if score ≥ 7 |
| GET  | `/jobs/log?n=50` | admin:admin | Last N job evaluations |

**Check the jobs log:**
```bash
curl -s -u admin:admin 'http://13.218.60.13:5555/jobs/log?n=20' | python3 -m json.tool
```

Each log entry: `id`, `received_at`, `score`, `is_fit`, `summary`, `reason`, `text_preview`.

**WA DM format sent to Fidel:**
```
🎯 *Job Alert* (score X/10)

*[Job title and org]*

_[One sentence reason for fit]_

---
[First 1000 chars of original post]
```

---

## Discord Agent Context (for follow-up analysis)

When Fidel receives a WA job alert and wants deeper analysis, he forwards it to the OpenClaw/Deepseek Discord agent. That agent has been briefed with:
- Fidel's background (African fantasy fiction author, Realms and Roads, MOSAS, ROTRQ)
- Role: deeper fit analysis, draft pitch letters on request
- No webhook integration needed — it operates on demand via Discord chat

---

## Deploying Changes to webhook.py

The master copy of `webhook.py` lives only on EC2 (not checked into this repo). To edit it:

```bash
# Pull it down
scp -i /tmp/ec2-temp-key ubuntu@13.218.60.13:/opt/indaba-jobs-webhook/webhook.py ~/Indaba/indaba-ec2/webhook.py

# Edit locally, then push back
scp -i /tmp/ec2-temp-key ~/Indaba/indaba-ec2/webhook.py ubuntu@13.218.60.13:/tmp/webhook_new.py
ssh -i /tmp/ec2-temp-key ubuntu@13.218.60.13 "sudo cp /tmp/webhook_new.py /opt/indaba-jobs-webhook/webhook.py && sudo systemctl restart indaba-jobs-webhook"
```

(Use the Instance Connect chain from the SSH section to get the key first.)

---

## Deploying Changes to sender.py

Master copy is at `~/Indaba/indaba-ec2/tmp/sender.py`. Edit locally, then:

```bash
# Full deploy snippet (from ~/Indaba):
cp ec2-key.pem /tmp/ec2-temp-key && chmod 600 /tmp/ec2-temp-key
PUB=$(ssh-keygen -y -f /tmp/ec2-temp-key)
aws ec2-instance-connect send-ssh-public-key \
  --instance-id i-0b381c5c13988ca76 \
  --instance-os-user ubuntu \
  --ssh-public-key "$PUB" \
  --region us-east-1 > /dev/null && \
scp -i /tmp/ec2-temp-key -o StrictHostKeyChecking=no \
  indaba-ec2/tmp/sender.py ubuntu@13.218.60.13:/tmp/sender_new.py && \
ssh -i /tmp/ec2-temp-key -o StrictHostKeyChecking=no ubuntu@13.218.60.13 \
  "sudo cp /tmp/sender_new.py /opt/indaba-sender/sender.py && sudo systemctl restart indaba-sender && sleep 2 && curl -s http://localhost:5555/health"
```
