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

## What's Next (Phase 4)

Phase 4 feature work can begin. Future coding sessions should use claude.ai/code.
Pushes to `main` auto-deploy within ~60 seconds — no manual SSH needed.

`localhost:5050` is retired. Use `https://indaba.realmsandroads.com`.
