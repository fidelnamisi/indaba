# Phase 6 Testing & Diagnostics

## Status: Nothing happens when sending messages to bot

The bot should respond to both `!commands` and natural language messages. If nothing is happening, follow this diagnostic sequence.

---

## Step 1: Verify EC2 Deployment

SSH to EC2 and check the bot service status:

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
sudo systemctl status indaba-discord
```

### Expected output:
```
● indaba-discord.service - Indaba Discord Bot
     Loaded: loaded (...)
     Active: active (running)
```

### If NOT running:

**Deploy the latest code:**
```bash
cd /opt/indaba-discord
git pull origin claude/discord-natural-language-2Xh4Y
sudo systemctl restart indaba-discord
```

**Check for errors:**
```bash
sudo journalctl -u indaba-discord -n 50 --follow
```

Watch for errors like:
- `ModuleNotFoundError: No module named 'anthropic'` → dependencies not installed
- `ANTHROPIC_API_KEY not found` → env var not set
- `DISCORD_BOT_TOKEN not found` → Discord token not set
- `ImportError` → syntax error in code

---

## Step 2: Verify Environment Variables

Check that tokens are set in the systemd service:

```bash
sudo systemctl cat indaba-discord | grep -E "DISCORD_BOT_TOKEN|ANTHROPIC_API_KEY"
```

### If missing:

Edit the service file:
```bash
sudo nano /etc/systemd/system/indaba-discord.service
```

Add/update these lines in the `[Service]` section:
```
Environment="DISCORD_BOT_TOKEN=your_actual_token_here"
Environment="ANTHROPIC_API_KEY=your_actual_key_here"
```

Then reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart indaba-discord
```

---

## Step 3: Test Bot Connectivity

In Discord, try the **read-only** `!` commands first (these don't require the agent):

- `!help` — should show the help message
- `!status` — should show EC2 sender health
- `!hub` — should show pipeline overview

### If `!` commands work but natural language doesn't:
The bot is running and connected. Problem is in the agent itself.

### If NO `!` commands work:
The bot isn't connected to Discord, or isn't in your channel. Check:
1. Is the bot online in Discord? (Check Server Members list)
2. Is it in the correct channel (#indaba-ops)?
3. Are the bot permissions correct? (Should have Send Messages, Read Message History)

---

## Step 4: Test Natural Language Agent

Once `!help` works, test natural language:

### Test A: Simple read-only request
```
"What's in the pipeline?"
```

**Expected:** Immediate response with pipeline summary (no "Say yes" prompt)

**If it fails:** Check EC2 logs for agent errors:
```bash
sudo journalctl -u indaba-discord -n 100 --follow
```

### Test B: Write operation with confirmation
```
"Generate the next proverb"
```

**Expected:** Bot shows preview text and ends with "Say 'yes' to confirm"

**If no response:** Agent is failing. Check logs.

**If response but no "Say yes":** System prompt didn't take effect.

### Test C: Confirmation flow
After Test B shows a preview, send:
```
"yes"
```

**Expected:** Proverb is queued and bot confirms with timestamp

**If "no":** The confirmation flow isn't working. The agent might not remember the context from the previous message.

---

## Step 5: Detailed Diagnostics

If tests are failing, enable verbose logging:

### Check bot stdout/stderr:
```bash
sudo journalctl -u indaba-discord -n 200 -o short-full
```

### Look for:
1. **Tool execution errors:** "Agent error: ..."
2. **API errors:** "HTTP 400", "HTTP 401"
3. **Missing variables:** "ANTHROPIC_API_KEY not set"
4. **Memory issues:** "history list has X items"
5. **Serialization errors:** "dict" vs "object" type mismatches

### Run a local test (on EC2):
```bash
cd /opt/indaba-discord
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
import claude_agent

# Test 1: Check if agent initializes
print("✓ claude_agent imported")

# Test 2: Check system prompt
print(f"System prompt length: {len(claude_agent.SYSTEM_PROMPT)} chars")

# Test 3: Check API key
from config import ANTHROPIC_API_KEY
if ANTHROPIC_API_KEY:
    print("✓ ANTHROPIC_API_KEY is set")
else:
    print("✗ ANTHROPIC_API_KEY is NOT set")

# Test 4: Check indaba client
import indaba_client as api
try:
    result = api.hub_summary()
    print(f"✓ Indaba API reachable: {len(result)} keys returned")
except Exception as e:
    print(f"✗ Indaba API failed: {e}")
EOF
```

---

## Step 6: Test Scenario Checklist

Once the bot is responding, run through these tests:

### ✅ Read-only operations (execute immediately):

- [ ] `"What's in the pipeline?"` → immediate response
- [ ] `"List all Love Back chapters in producing"` → immediate response  
- [ ] `"Show me promo status"` → immediate response
- [ ] `!hub` → immediate response (should work)
- [ ] `!status` → immediate response (should work)

### ✅ Write operations (preview + confirm):

- [ ] `"Generate the next proverb"` → shows preview → "yes" → queued
- [ ] `"Publish chapter 3 of Love Back"` → shows preview → "yes" → published
- [ ] `"Move OAO ch5 to publishing"` → confirms move → "yes" → moved

### ✅ Cancellation:

- [ ] `"Generate a proverb"` → preview → `"no"` or `"skip"` → cancelled, no action taken

### ✅ Multi-turn context:

- [ ] `"Generate 2 proverbs"` → preverb 1 → `"yes"` → queued → preview 2 → `"yes"` → queued

### ✅ History persistence (in same channel):

- [ ] `"Generate a proverb"` → preview → `"yes"` → success
- [ ] 5 minutes later, `"Generate another"` → bot still responds (history wasn't cleared)

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| "Agent error: ANTHROPIC_API_KEY not set" | Env var missing | Set in systemd service, reload, restart |
| No bot response at all | Bot not running | Check `systemctl status`, redeploy |
| `!help` works but natural language doesn't | Agent failing | Check logs for errors |
| "Say yes" prompt doesn't appear | System prompt not updated | Check git pull worked, service restarted |
| Agent doesn't remember previous message (says "yes" but fails) | History not persisting | Check _channel_history dict in bot.py (should have persisted between messages) |
| Agent loops forever or times out | Too many tool calls | Check API response format, max tool calls is 20 |

---

## Recovery: Force Restart

If the bot is stuck:

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
sudo systemctl stop indaba-discord
sudo systemctl start indaba-discord
sudo systemctl status indaba-discord
```

Then test again with `!help` or a simple message.
