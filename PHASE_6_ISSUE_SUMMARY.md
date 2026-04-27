# Phase 6: Issue Summary & Diagnostics

## Problem Statement
"Nothing happens at all on Discord when I send any commands to @Indaba Bot"

---

## What This Means

### Scenario 1: All messages are ignored
- ✗ `!help` produces no response
- ✗ `"Generate a proverb"` produces no response  
- ✓ Bot is online in Discord (appears in member list)

**Root Cause:** Bot service crashed, not running, or no longer connected

### Scenario 2: `!` commands work but natural language doesn't
- ✓ `!help` works, `!status` works, `!hub` works
- ✗ `"Generate a proverb"` produces no response

**Root Cause:** Natural language handler is crashing or agent is broken

### Scenario 3: Messages are being read but processing fails silently
- ✓ Bot reads messages (you see the message sent in Discord)
- ✗ No response, not even "Working..."
- No error message

**Root Cause:** Exception in `_handle_natural_language()` not being caught, or message processing fails before the "Working..." status message

---

## Most Likely Culprits (in order of probability)

### 1. **Code Not Deployed to EC2** (60% likely)

The changes were committed locally but not pushed to EC2.

**Verify:**
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
cd /opt/indaba-discord
git log -1
# Should show: "Phase 6: Natural language Discord bot with per-channel memory and confirmation flow"
```

**If not deployed:**
```bash
cd /opt/indaba-discord
git pull origin claude/discord-natural-language-2Xh4Y
sudo systemctl restart indaba-discord
```

### 2. **History Serialization Bug** (25% likely)

I added code to convert SDK objects to dicts for storage. This is necessary but might have a bug.

**Symptom:** Bot crashes on first natural language message

**Check logs:**
```bash
sudo journalctl -u indaba-discord -n 100
```

**Look for:**
- `TypeError: 'dict' object has no attribute 'text'`
- `AttributeError: ...`
- Traceback showing `_content_block_to_dict`

**If found:** The conversion helpers need fixing

### 3. **Missing Dependencies on EC2** (10% likely)

The anthropic package or another dependency isn't installed.

**Check:**
```bash
cd /opt/indaba-discord
python3 -c "import anthropic; print('OK')"
```

**If fails:**
```bash
pip install -r requirements.txt
sudo systemctl restart indaba-discord
```

### 4. **Environment Variables Not Set** (5% likely)

ANTHROPIC_API_KEY or DISCORD_BOT_TOKEN not set in the systemd service.

**Check:**
```bash
sudo systemctl cat indaba-discord | grep Environment
```

**If ANTHROPIC_API_KEY is missing:**
```bash
sudo nano /etc/systemd/system/indaba-discord.service
# Add: Environment="ANTHROPIC_API_KEY=<key>"
sudo systemctl daemon-reload
sudo systemctl restart indaba-discord
```

---

## Immediate Action Plan

### Step 1: Check service status
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
sudo systemctl status indaba-discord
```

If it says **"inactive (dead)"** or **"failed"**, the service crashed. Go to Step 3.  
If it says **"active (running)"**, go to Step 2.

### Step 2: Check if code is deployed
```bash
cd /opt/indaba-discord
git log -1 --oneline
```

Should mention "Phase 6" or "natural language".

If not, deploy:
```bash
git pull origin claude/discord-natural-language-2Xh4Y
sudo systemctl restart indaba-discord
```

### Step 3: Check logs for errors
```bash
sudo journalctl -u indaba-discord -n 50 --no-pager
```

Look for:
- `ImportError` → dependency missing
- `ANTHROPIC_API_KEY` → env var missing
- `Traceback` → code error
- `TypeError`, `AttributeError` → serialization bug

### Step 4: Test bot functionality
In Discord:
- Try `!help` (read-only, no agent)
- If that works, try `"What's in the pipeline?"` (read-only, uses agent)
- If that fails, natural language is broken

### Step 5: Enable debug logging

If still stuck, add temporary debug output to `bot.py`:

```python
async def _handle_natural_language(message: discord.Message):
    print(f"DEBUG: Natural language message: {message.content[:50]}")
    channel_id = message.channel.id
    history = _channel_history.get(channel_id, [])
    print(f"DEBUG: History has {len(history)} messages")
    # ... rest of function
```

Then:
```bash
cd /opt/indaba-discord
sudo systemctl restart indaba-discord
sudo journalctl -u indaba-discord -f
# Watch the output as you send messages
```

---

## Expected Behavior When Fixed

### Test 1: Read-only query
```
User: "What's in the pipeline?"
Bot: *Working…*
     (updates after 2-3 seconds)
     "**Pipeline** (15 entries)
     [LB] Glass Hearts...
     "
```

### Test 2: Write operation with confirmation
```
User: "Generate the next proverb"
Bot: *Working…*
     (updates after 3-5 seconds)
     "**Preview - Proverb Broadcast**
     ...caption and image details...
     Say 'yes' to confirm or 'no' to cancel."

User: "yes"
Bot: *Working…*
     "Done. Queued for [timestamp]"
```

### Test 3: Cancellation
```
User: "Generate a proverb"
Bot: "**Preview - Proverb Broadcast**
     ...
     Say 'yes' to confirm or 'no' to cancel."

User: "no thanks"
Bot: "Cancelled. Would you like a different proverb?"
```

---

## Communication Expected

Once `_handle_natural_language()` is properly running:

1. **On every non-`!` message:** Bot immediately responds with *"Working…"* placeholder
2. **Within 2-5 seconds:** Placeholder updates with the actual response
3. **Multi-turn awareness:** Bot remembers previous messages in the channel for context

---

## Files to Review

If debugging locally:

- `discord_bot/bot.py` — contains `_handle_natural_language()` and `_channel_history`
- `discord_bot/claude_agent.py` — contains `run_agent()`, system prompt, and serialization helpers
- `/etc/systemd/system/indaba-discord.service` (on EC2) — contains environment variables
- `discord_bot/requirements.txt` — lists dependencies

---

## Quick Recovery

If all else fails:

```bash
# Force restart the service
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
sudo systemctl restart indaba-discord
sleep 2
sudo systemctl status indaba-discord

# View live logs
sudo journalctl -u indaba-discord -f
```

Then in Discord, send a test message and watch the logs for errors.
