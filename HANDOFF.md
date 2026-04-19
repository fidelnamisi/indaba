# Indaba Handoff Log

---

## 2026-04-19 — Discord Bot + EC2 Indaba Deployment

### What was built

**Indaba Bot** — a Discord bot that lets you operate Indaba from any Discord channel, 24/7, even when your Mac is off.

---

### Architecture

```
Discord (your phone / any device)
        │
        ▼
Indaba Bot (EC2 /opt/indaba-discord, port — none, systemd service: indaba-discord)
        │
        ├──► Indaba Flask API (EC2 /opt/indaba-app:5050, systemd service: indaba-app)
        │         └── data/ seeded from Mac on 2026-04-19 (74 pipeline entries)
        │
        └──► EC2 Sender health (localhost:5555)
```

The Mac stays your **development** instance. EC2 is the **ops** instance. They share the same GitHub repo but have independent data directories. When the Mac modifies data, push to GitHub and re-seed EC2 if needed.

---

### Activating the Bot — One-Time Setup Required

The bot code is deployed and ready. You just need a Discord token:

**Step 1 — Create the Discord Application**
1. Go to https://discord.com/developers/applications
2. Click "New Application" → name it "Indaba Bot"
3. Go to "Bot" tab → click "Add Bot"
4. Under "Privileged Gateway Intents" enable **Message Content Intent**
5. Copy the **Bot Token**

**Step 2 — Invite the Bot to your Server**
1. Go to "OAuth2" → "URL Generator"
2. Scopes: `bot`
3. Bot Permissions: `Send Messages`, `Read Message History`, `View Channels`
4. Copy the URL and open it → select your server

**Step 3 — Create the #indaba-ops channel** in your Discord server

**Step 4 — Add the token to EC2**
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
sudo nano /etc/systemd/system/indaba-discord.service
# Replace: DISCORD_BOT_TOKEN=PASTE_TOKEN_HERE
# With:    DISCORD_BOT_TOKEN=your_actual_token
sudo systemctl daemon-reload
sudo systemctl start indaba-discord
sudo systemctl status indaba-discord
```

**Step 5 — (Optional) Enable GitHub push from bot's `!idea` command**
```bash
# Create a GitHub Personal Access Token with repo scope at github.com/settings/tokens
sudo nano /etc/systemd/system/indaba-discord.service
# Set GITHUB_TOKEN=your_github_pat
sudo systemctl daemon-reload && sudo systemctl restart indaba-discord
```

---

### Bot Commands

| Command | What it does |
|---------|-------------|
| `!hub` | Pipeline overview (producing/publishing/promoting counts) |
| `!pipeline [book] [stage]` | List pipeline entries, optionally filtered |
| `!entry <id>` | Get details on one pipeline entry |
| `!stage <id> <stage>` | Move entry to producing\|publishing\|promoting |
| `!publish <id>` | Publish chapter to realmsandroads.com |
| `!deploy` | Deploy website to AWS Amplify |
| `!deploystatus` | Check deploy status |
| `!sync <work_code>` | Compare pipeline vs live website |
| `!works` | List all book series |
| `!status` | EC2 sender health |
| `!idea <text>` | Capture idea → ROADMAP.md → GitHub |
| `!help` | Full command list |

Natural language also works — any message not starting with `!` is parsed by Claude Haiku.

**Book codes:** LB, OAO, ROTRQ, MOSAS  
**Stages:** producing, publishing, promoting

---

### EC2 Services Summary

| Service | Location | Port | Status |
|---------|----------|------|--------|
| `indaba-app` | `/opt/indaba-app` | 5050 | ✅ running |
| `indaba-discord` | `/opt/indaba-discord` | — | ⏸ waiting for DISCORD_BOT_TOKEN |
| `indaba-sender` | `/opt/indaba-sender` | 5555 | ✅ running (existing) |

Check all services: `sudo systemctl status indaba-app indaba-discord indaba-sender`

---

### Files Added

| File | Purpose |
|------|---------|
| `discord_bot/bot.py` | Main Discord bot |
| `discord_bot/indaba_client.py` | HTTP wrapper for Indaba API |
| `discord_bot/claude_agent.py` | Claude Haiku NLP parser |
| `discord_bot/roadmap.py` | ROADMAP.md idea capture + git push |
| `discord_bot/config.py` | Env var configuration |
| `discord_bot/indaba-app.service` | Systemd service for EC2 Indaba |
| `discord_bot/indaba-discord.service` | Systemd service for Discord bot |
| `ROADMAP.md` | Idea capture file — appended by `!idea` |

---

### Data Sync (Mac ↔ EC2)

Data lives in `data/` which is gitignored. Current approach:
- Mac is dev, EC2 is ops — they may diverge over time
- To push Mac data to EC2: `rsync -av --include='*.json' --exclude='*' data/ ubuntu@13.218.60.13:/opt/indaba-app/data/` (using the permanent key installed today)
- To pull EC2 data to Mac: reverse the above
- SSH key is now **permanent** — no more 60-second EC2 Instance Connect dance

---

### SSH Access (Updated)

The EC2 SSH key is now permanent. Direct SSH works without Instance Connect:
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
```

No more `aws ec2-instance-connect send-ssh-public-key` needed.

---

## 2026-04-17 — Chapter HTML Template Bug Fixes

**File:** `services/chapter_html_template.py`

### Bug 1 — Wrong callout class (`patreon-callout` → `support-callout`) ✅ FIXED

**What happened:** The chapter template rendered a `<div class="patreon-callout">` block with a hardcoded Patreon link.

**Why it was wrong:** `main.js` on realmsandroads.com looks for `.support-callout` and replaces its content dynamically based on the reader's membership tier. With the wrong class, JS never fired and readers saw a hardcoded Patreon link instead of the correct membership CTA.

**Fix applied:** Replaced the block with:
```html
<div class="support-callout">
  <h3>Enjoying the story?</h3>
  <p>Support the creation of more stories — become a member and get early access to new chapters.</p>
  <a href="/subscribe.html" class="btn btn-primary">Join Today ›</a>
</div>
```

**Rule:** Never use `.patreon-callout` or reference `patreon.com` in any chapter template.

---

### Bug 2 — Unstripped markdown in chapter body ✅ FIXED

**What happened:** Content fields containing standalone markdown bold lines (e.g. `**Glass Hearts**`) were passed verbatim into `<p>` tags. The site has no markdown renderer, so asterisks were displayed raw to readers.

**Fix applied:** `prose_to_html()` now skips any paragraph that is a standalone markdown bold/italic line (regex: `^\*{1,3}.+\*{1,3}$`). These lines are chapter title echoes — the title is already rendered in the `<h1>` above the article.

**Broader rule:** Content arriving at the publish endpoint should be plain prose. Any standalone `**title**` lines at the top of a content field are dropped before HTML rendering.
