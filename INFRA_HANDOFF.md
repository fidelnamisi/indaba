# Infra Bootstrap Handoff
**Date:** 2026-04-27
**Follows:** Phase 3 (PHASE_3_HANDOFF.md)
**Precedes:** Phase 4 feature work

---

## Context

Phase 3 completed all feature development. Before resuming Phase 4, two
infrastructure decisions were made:

1. **Single source of truth:** The Indaba dashboard must live at
   `https://indaba.fidelnamisi.com` (EC2-hosted). Local `localhost:5050`
   is retired as the primary interface.

2. **Claude Code on the web:** Future coding phases will run via
   `claude.ai/code` (browser-based), NOT via CLI installed on EC2.
   This requires GitHub Actions auto-deploy so that a web Claude Code
   push to GitHub automatically restarts services on EC2.

---

## Current State

| Thing | State |
|-------|-------|
| EC2 IP | 13.218.60.13 |
| indaba-app | Running on EC2:5050, healthy |
| indaba-discord | Running on EC2, 27 tools |
| indaba-sender | Running on EC2:5555 |
| nginx on EC2 | NOT installed |
| indaba.fidelnamisi.com DNS | NOT yet pointed at EC2 |
| GitHub Actions deploy | NOT set up |
| Local vs EC2 data | Local has authoritative leads/contacts; EC2 has authoritative proverbs |

---

## What the Next Session Must Do

### Part 1 — indaba.fidelnamisi.com (do this first, it is urgent)

**Fidel must do before the session starts:**
- Add an A record at your domain registrar:
  `indaba.fidelnamisi.com → 13.218.60.13`
- Confirm the record is live (propagation can take minutes to an hour):
  `dig indaba.fidelnamisi.com +short` should return `13.218.60.13`

**Claude does in session:**
1. Install nginx on EC2
2. Configure nginx: proxy `indaba.fidelnamisi.com:80` → `localhost:5050`
3. Install certbot, obtain SSL cert, redirect HTTP → HTTPS
4. Run `./scripts/sync_to_ec2.sh` to push leads + contacts to EC2
5. Smoke-test: `curl -s https://indaba.fidelnamisi.com/api/hub/summary`
   → expect 200

### Part 2 — Claude Code on the web auto-deploy

**Claude does in session:**
1. Create `.github/workflows/deploy.yml`:
   - Trigger: push to `main`
   - Action: SSH to EC2, `git pull`, `pip install -r requirements.txt`,
     `sudo systemctl restart indaba-app indaba-discord`
2. Write `/opt/indaba-app/CLAUDE.ec2.md` (ops context for web Claude Code)
3. Update Discord bot `EC2_INDABA_URL` env var to point to
   `https://indaba.fidelnamisi.com` instead of `http://localhost:5050`
4. Test: push a trivial commit, confirm EC2 auto-restarts within 60s

**Fidel must do (can't be done by Claude):**
- Add two GitHub Actions secrets in the repo settings
  (github.com → fidelnamisi/indaba → Settings → Secrets → Actions):
  - `EC2_SSH_KEY` — paste the full contents of `~/Indaba/ec2-key.pem`
  - `EC2_HOST` — `ubuntu@13.218.60.13`

---

## SSH Access (unchanged)

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
```

---

## Files Changed This Session (Phase 3)

| File | Change |
|------|--------|
| `routes/promo_broadcast_post.py` | Added `generate_batch` route |
| `routes/promo_messages.py` | Added `inbound` route |
| `discord_bot/claude_agent.py` | Added `proverbs_generate_batch` tool (#27) |
| `discord_bot/indaba_client.py` | Added `proverbs_generate_batch()` |
| `scripts/sync_to_ec2.sh` | New — pushes mutable data to EC2 |
| `CLAUDE.md` | Added data sync architecture table |
| `services/distribution_service.py` | Deployed to EC2 (was missing `fetch_ec2_queue`) |
