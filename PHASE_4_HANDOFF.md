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

## Phase 4 Status (Updated 2026-04-27)

**✅ Data Sync Complete:** All 20 missing/truncated files copied from localhost to EC2.
Hub summary pipeline counts now match (62 producing, 6 promoting, 6 publishing).

**⚠️ Pending Issues (2):**
1. **Messages Queue Discrepancy:** EC2 shows 14 queued vs localhost 22 — investigation needed
2. **Port Race Condition:** GitHub Actions deploy doesn't kill old process, causing port 5051 binding

**👉 See `PHASE_4_DATA_SYNC_HANDOFF.md` for detailed issue descriptions and resolution steps.**

After next session resolves both issues:
- EC2 and localhost will be in full parity
- `localhost:5050` can be retired
- Future coding sessions should use `claude.ai/code` (auto-deploy within ~60 seconds)

---

## What's Next (Phase 4 Final Steps)

**Next Session:**
1. Diagnose messages queue discrepancy (check migrate.py, sync logic)
2. Harden GitHub Actions deploy script to kill old processes before restart
3. Verify both issues resolved with final validation test
4. Mark Phase 4 complete

See `PHASE_4_DATA_SYNC_HANDOFF.md` for copy-paste instructions.
