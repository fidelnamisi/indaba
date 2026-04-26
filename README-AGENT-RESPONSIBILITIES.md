# Indaba: Application Agent Folder

This folder is reserved for **application layer and UI/dashboard work**.

## What Lives Here

- **HANDOFF.md** — Complete application layer handoff documentation (start here)
- **app.py** — Main Indaba Flask application (port 5050)
- **templates/** — HTML templates for dashboard and publishing interface
- **static/** — CSS, JavaScript, and frontend assets
- **data/** — JSON data files (content pipeline, promo settings, etc.)
- **com.fidel.indaba.plist** — LaunchAgent for auto-starting the app

## What This Agent Does

- Indaba app features and bug fixes (Flask routes, templates, API endpoints)
- Dashboard UI updates and refinements
- Content pipeline management and publishing workflows
- WhatsApp channel integration and promo settings
- Frontend JavaScript and styling

## What This Agent DOES NOT Do

EC2 infrastructure work, sender microservice updates, GoWA integration, SSH deployment, or message queue management. That's in the sibling folder.

## Reference Folders

- **../indaba-ec2/** — Infrastructure layer (EC2, sender microservice, GoWA)
- **../image-gen-mcp/** — Image generation MCP server

## Getting Started

1. Read **HANDOFF.md** (this folder)
2. Understand **data/content_pipeline.json** structure
3. Review **app.py** for current endpoints and logic
4. For infrastructure questions, reference **../indaba-ec2/HANDOFF-EC2.md**

---

**Next agent: When starting work here, run from this directory:**
```bash
cd ~/Indaba
claude  # Will pick up HANDOFF.md automatically
```
