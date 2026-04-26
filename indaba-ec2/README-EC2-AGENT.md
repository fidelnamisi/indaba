# indaba-ec2 — Infrastructure Agent Folder

This subfolder is reserved for **EC2 microservice and infrastructure work**.

## What Lives Here

- **HANDOFF-EC2.md** — Complete infrastructure handoff documentation (start here)
- **ec2-key.pem** — SSH private key for EC2 access
- **tmp/sender.py** — Master copy of the EC2 sender microservice (Flask app, port 5555)

## Agent Scope

You work on:
- EC2 sender microservice updates (port 5555)
- GoWA integration and device UUID management
- Message queue health monitoring
- EC2 deployment and SSH access
- Infrastructure troubleshooting

You do NOT work on:
- Application layer (Flask app on port 5050)
- UI/dashboard updates
- Content pipeline or publishing workflows
- Indaba app logic

---

## Getting Started

1. **Start here:** Read **HANDOFF-EC2.md** in this folder
2. **Understand the workflow:** Review EC2 details, SSH access pattern, and device UUID self-healing
3. **Check the deployment flow:** See Section 6 (Deploying sender.py Changes)
4. **For app-layer questions:** Reference **../HANDOFF.md**

---

## Running Claude Code

Run from this directory:
```bash
cd ~/Indaba/indaba-ec2
claude
```

Claude Code will automatically read HANDOFF-EC2.md.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| HANDOFF-EC2.md | Your complete handoff (architecture, SSH, endpoints, deployment) |
| tmp/sender.py | Master copy of sender microservice — edit here, deploy to EC2 |
| ec2-key.pem | Private key for SSH access to 13.218.60.13 |

---

## Cross-Reference

- **App Layer:** See `../HANDOFF.md` for Flask app, UI, dashboard work
- **Indaba Root:** `../app.py`, `../static/`, `../templates/` (don't touch from this folder)
