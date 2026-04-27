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

## What's Next (Phase 4)

**Before feature work begins:** Run a full end-to-end comparison between
`localhost:5050` and `https://indaba.realmsandroads.com` to surface all defects in
the EC2 version. Known issue already identified: People > Contacts is empty on EC2
(data sync may be incomplete or a route is broken).

See `PHASE_4_TEST_INSTRUCTIONS.md` for the full testing brief.

After testing is complete and defects are fixed, `localhost:5050` can be retired.
Future coding sessions should use `claude.ai/code` — pushes to `main` auto-deploy
within ~60 seconds, no SSH needed.
