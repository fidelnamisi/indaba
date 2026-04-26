# Indaba — BUILD Workspace

> **This is the BUILD workspace.** You are here to develop and maintain Indaba's
> codebase. You may read and write source files, routes, services, data files,
> and tests freely.
>
> **To operate Indaba** (publish chapters, manage pipeline, deploy):
> exit this session and run `cd ~/Indaba-ops && claude`
>
> Never perform publishing operations or pipeline data edits here unless
> Fidel explicitly asks you to as part of a development task.

---

## ⚠️ Read This First — Every Session

At the start of every session where Indaba work is in scope, read the SLA before doing anything else:

**`./indaba-sla.md`**

This is a living Service Level Agreement between Fidel and Claude. It contains:
- Active accountability commitments (things Claude surfaces so Fidel can act)
- Active automation commitments (things Claude handles independently)
- A session start protocol (what to report and ask)
- A completed items log

After reading it, briefly surface any items that need attention (stalled chapters, days since last WA post, pending automation tasks) and ask Fidel which he wants to act on today.

Do not skip this step.

---

## Project Overview

**Indaba** is a self-hosted personal productivity and publishing dashboard for a professional writer.

- **Backend:** Python / Flask, port 5050, file: `app.py`
- **Frontend:** Vanilla JS (no framework), `static/app.js`
- **Styles:** `static/style.css`
- **Data:** JSON files in `data/` — written atomically via `os.replace()`

## Reference Files

- `./indaba-sla.md` — Active SLA (read every session)
- `./AGENT_INSTRUCTIONS.md` — Full feature implementation brief
- `./indaba-implementation-brief.md` — Extended system context and architecture
- `./data/content_pipeline.json` — 53 chapters with publish statuses and assets
- `./data/promo_settings.json` — WA channel branding, AI provider config
- `./data/promo_proverbs.json` — Proverb library for WA channel

## Key Data Files

| File | Purpose |
|------|---------|
| `content_pipeline.json` | Chapter publishing pipeline (OAO, ROTRQ, MOSAS) |
| `promo_proverbs.json` | Proverbs for daily WA channel posts |
| `posting_log.json` | Log of what has been posted and when |
| `promo_settings.json` | WA channel branding + AI provider settings |
| `projects.json` | Active and completed projects |
| `lead_measures.json` | Weekly lead measure tracking |
| `earnings.json` | Monthly Patreon earnings |

## Data Sync Architecture

Local and EC2 are **separate data stores**. Use `./scripts/sync_to_ec2.sh` to push mutable files.

| File | Authoritative source | Notes |
|------|---------------------|-------|
| `promo_leads.json` | **Local** | Edit in dashboard, push to EC2 after changes |
| `promo_contacts.json` | **Local** | Edit in dashboard, push to EC2 after changes |
| `promo_proverbs.json` | **EC2** | Bot adds proverbs on EC2; pull from EC2 if needed |
| `promo_messages.json` | **EC2** | Outbox lives on EC2; do not overwrite |
| `content_pipeline.json` | **Local** | Chapter pipeline is local-only |

## Development Rules

- Read every file before modifying it
- Use atomic writes: write to `.tmp`, then `os.replace()`
- Run `migrate()` for any data model changes
- Never break existing API endpoints
