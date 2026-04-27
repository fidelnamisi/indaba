# Infra Bootstrap Handoff → Phase 4
**Date:** 2026-04-27
**Session:** Infra Bootstrap
**Follows:** Phase 3 (PHASE_3_HANDOFF.md)

---

## What Was Set Up

### 1. indaba.realmsandroads.com (Live)

| Step | Result |
|------|--------|
| DNS A record | `indaba.realmsandroads.com → 13.218.60.13` (added by Fidel via Route 53) |
| Security group | Ports 80 + 443 opened on `indaba-sender-sg` (sg-023898d082b798b15) |
| nginx | Installed, site config written, default site removed |
| SSL cert | Let's Encrypt cert issued via certbot; auto-renews; expires 2026-07-26 |
| HTTP → HTTPS | certbot configured nginx to redirect port 80 → 443 |
| Smoke test | `curl https://indaba.realmsandroads.com/api/hub/summary` → 200 |
| Data sync | `sync_to_ec2.sh` pushed leads, contacts, proverbs to EC2 |

### 2. GitHub Actions Auto-Deploy

File: `.github/workflows/deploy.yml`

- Trigger: push to `main`
- Action: SSH to EC2, `git pull origin main`, `pip install`, `systemctl restart indaba-app`
- Secrets required (already added by Fidel): `EC2_SSH_KEY`, `EC2_HOST`

### 3. Discord Bot Updated

- `INDABA_BASE_URL` updated from `http://localhost:5050` → `https://indaba.realmsandroads.com`
- Service restarted and confirmed `active`

### 4. CLAUDE.ec2.md Written on EC2

Location: `/opt/indaba-app/CLAUDE.ec2.md`

Ops context for future Claude Code web sessions — explains auto-deploy, service names, live URL.

---

## Current State

| Thing | State |
|-------|-------|
| EC2 IP | 13.218.60.13 |
| Live URL | https://indaba.realmsandroads.com |
| indaba-app | Running on EC2:5050, proxied via nginx/HTTPS |
| indaba-discord | Running, pointing at realmsandroads.com URL |
| indaba-sender | Running on EC2:5555 |
| nginx | Installed, HTTPS configured |
| SSL cert | Active, auto-renewing |
| GitHub Actions deploy | Active — push to main auto-restarts indaba-app |
| Local vs EC2 data | In sync (leads, contacts, proverbs pushed) |

---

## SSH Access

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
```

---

## Known Issue: Auto-Deploy Port Race Condition

When GitHub Actions restarts `indaba-app`, if the old process is still alive, the new one
binds to port 5051 instead of 5050, causing 502 errors. Fix: pre-kill the process before
restart. The deploy script should be hardened in Phase 4.

**Workaround if you see 502 after a push:**
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 \
  'sudo kill $(sudo lsof -ti:5051) 2>/dev/null; sudo systemctl restart indaba-app'
```

---

## Phase 4 Status — COMPLETE ✅ (2026-04-27)

### Issues Resolved

**✅ Data Sync Complete:** All 20 missing/truncated files copied from localhost to EC2. Hub summary pipeline counts verified (62 producing, 6 promoting, 6 publishing).

**✅ Messages Queue Discrepancy FIXED:**
- Root cause: `process_overdue_queue()` in migrate.py correctly marks messages with past `scheduled_at` times as "overdue"
- 8 messages with April 25-27 scheduled times were converted from queued → overdue
- Result: Both localhost and EC2 now show **messages_queued = 14** (correct)
- Workflow: `utils/helpers.py:process_overdue_queue()` → marks past-scheduled messages as overdue
- This is **correct behavior**, not a bug

**✅ Port Race Condition FIXED:**
- Commit `270ec81`: Deploy script now kills old Python processes before restart
- Updated `.github/workflows/deploy.yml` to add:
  - `sudo pkill -9 -f "python.*app.py"`
  - `sudo lsof -i :5050 -S -t | xargs -r kill -9`
  - `sudo lsof -i :5051 -S -t | xargs -r kill -9`
- Ensures service restart always binds to port 5050
- GitHub Actions auto-deploy now works reliably

### Final Validation (2026-04-27)
```
✅ LOCALHOST: messages_queued=14, pipeline=62/6/6, API responding
✅ EC2:       messages_queued=14, pipeline=62/6/6, API responding
✅ Deploy:    Fixed, tested, and pushed to main
```

---

## What's Next

**Phase 5: Discord Bot Testing** — See `PHASE_5_DISCORD_BOT_TESTING.md`

Next session will:
1. Use Claude Code on the web (Haiku model)
2. Test all Discord bot functionalities end-to-end
3. Document which workflows pass/fail
4. Report findings for Sonnet to fix in follow-up session
