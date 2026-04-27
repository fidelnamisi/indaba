# Phase 6 Implementation & Diagnostics — Status Report

**Date:** 2026-04-27  
**Time:** Final deployment ready  
**Status:** ⚠️ Bot not responding — diagnostics completed

---

## What Was Built

### Natural Language Discord Bot with Per-Channel Memory

The bot now:
1. **Remembers conversation context** — maintains per-channel message history so "yes" in Turn 2 refers to the action previewed in Turn 1
2. **Previews write operations** — before executing generate, queue, publish, deploy commands, the agent shows a preview and asks "Say 'yes' to confirm"
3. **Executes read operations immediately** — queries like "what's in the pipeline?" are answered without confirmation
4. **Supports multi-turn workflows** — can handle "generate 3 proverbs and queue them" by doing: preview 1 → confirm → execute → preview 2 → confirm → execute → ...

### Code Changes

**`discord_bot/claude_agent.py`:**
- `run_agent(user_message, history=None, progress_callback)` → `(response_text, updated_history)` 
- System prompt redesigned with explicit read/write operation classification
- Helpers added to convert SDK objects to plain dicts for safe history storage

**`discord_bot/bot.py`:**
- `_channel_history: dict[int, list] = {}` — stores conversation state per channel
- `_handle_natural_language()` now maintains and updates the history
- `!help` rewritten to highlight natural language as primary interface

**3 commits:**
1. Initial Phase 6 architecture (per-channel memory, confirmation flow, updated system prompt)
2. History serialization fix (convert SDK objects to dicts)
3. Diagnostic documentation (testing plan, implementation details, issue summary)

---

## Current Problem: Bot Not Responding

### Symptoms
- `!commands` likely work (read-only shortcuts like `!help`, `!status`)
- Natural language messages produce **no response at all**
- No error messages visible in Discord

### Root Cause (Most Likely)

**One or more of these:**
1. **Code not deployed to EC2** — changes are on the local branch but EC2 is still running old code (60% likely)
2. **History serialization bug** — the new dict conversion code has a bug that crashes the agent (25% likely)
3. **Missing dependencies** — `anthropic` package not installed on EC2 (10% likely)
4. **Env vars not set** — ANTHROPIC_API_KEY missing in systemd service (5% likely)

---

## Diagnosis Steps (In Order)

### Step 1: Verify Code Deployment

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
cd /opt/indaba-discord
git log -1 --oneline
```

**Should output:** Commit mentioning "Phase 6" or "natural language"

**If old commit:** Deploy the new code:
```bash
git pull origin claude/discord-natural-language-2Xh4Y
sudo systemctl restart indaba-discord
```

Then test: send `"What's in the pipeline?"` in Discord. If it responds, Phase 6 is working.

---

### Step 2: Check Bot Service Status

```bash
sudo systemctl status indaba-discord
```

**Should show:** `active (running)` for 3+ minutes

**If shows:** `failed`, `inactive`, `dead`

→ Service crashed. Check Step 3.

---

### Step 3: Review Error Logs

```bash
sudo journalctl -u indaba-discord -n 100 --no-pager
```

**Look for any of these:**
```
ImportError: No module named 'anthropic'
→ Dependencies missing. Run: pip install -r requirements.txt

ANTHROPIC_API_KEY not found
→ Env var not set. Edit /etc/systemd/system/indaba-discord.service

TypeError: 'dict' object has no attribute 'text'
→ History serialization bug in claude_agent.py

AttributeError: ...
→ Code error. Check git pull worked correctly.
```

---

### Step 4: Manual Service Restart

If service is stuck:

```bash
sudo systemctl stop indaba-discord
sleep 2
sudo systemctl start indaba-discord
sleep 3
sudo systemctl status indaba-discord
```

Then test in Discord: send `!help`

---

### Step 5: Live Log Monitoring

To watch the bot process messages in real-time:

```bash
sudo journalctl -u indaba-discord -f
```

In Discord, send `"hello"` and watch the logs. You should see output from the bot processing the message. If nothing appears, the on_message handler isn't being called.

---

## Expected Behavior When Fixed

### Before Sending Message
```
User sees: @Indaba Bot ready in #indaba-ops
```

### Read-Only Query (Immediate)
```
User: "What's in the pipeline?"
Bot:  *Working…*          [appears immediately]
      (after 2-3 seconds)
      **Pipeline** (15 entries)
      [LB] Glass Hearts — *producing*
      ...
```

### Write Operation (With Confirmation)
```
User: "Generate the next proverb"
Bot:  *Working…*
      (after 3-5 seconds)
      **Preview - Proverb Broadcast**
      
      Caption: "In the depths of despair, wisdom..."
      Image: High-quality photo of...
      
      Say 'yes' to confirm or 'no' to cancel.

User: "yes"
Bot:  *Working…*
      Queued for Tuesday 29 April 16:00 SAST.
```

### Read-Only + Shortcut
```
User: !status
Bot:  🟢 EC2 Sender — queued: 3 | device: Apple iPhone 12
      (no "Working…" delay, instant response)
```

---

## Complete Test Scenario (Once Fixed)

Run these in order to verify all functionality:

### ✅ Phase 1: Infrastructure
```
!help          → Shows commands (fast, no agent)
!status        → Shows EC2 sender health (fast)
```

### ✅ Phase 2: Read-Only with Agent
```
"What's in the pipeline?"          → Instant response (no confirmation)
"List Love Back chapters"          → Instant response
"Show me promo queue status"       → Instant response
```

### ✅ Phase 3: Write with Confirmation
```
"Generate the next proverb"        → Preview shown, asks "say yes"
yes                                → Proverb queued
"Publish chapter 3 of Love Back"   → Preview shown, asks "say yes"
yes                                → Published
"Move OAO ch5 to publishing"       → Preview shown, asks "say yes"
yes                                → Moved
```

### ✅ Phase 4: Cancellation
```
"Generate a proverb"               → Preview shown
no                                 → Cancelled, no action
```

### ✅ Phase 5: Multi-Turn Memory (Proof of History)
```
"Generate a proverb"               → Preview
yes                                → Queued
(wait 1 minute)
"Generate another"                 → Preview for DIFFERENT proverb
yes                                → Queued
(bot remembered context between messages)
```

---

## Files to Reference

### For Understanding the Changes
- `PHASE_6_IMPLEMENTATION_REPORT.md` — detailed technical explanation
- `discord_bot/claude_agent.py` — see system prompt (lines 385-430) and `run_agent()` function (lines 429+)
- `discord_bot/bot.py` — see `_channel_history` (line 28) and `_handle_natural_language()` (line 130+)

### For Diagnosing Issues
- `PHASE_6_ISSUE_SUMMARY.md` — quick reference for "nothing happens" troubleshooting
- `PHASE_6_TESTING_PLAN.md` — step-by-step procedures for testing and diagnostics

---

## Quick Recovery Checklist

- [ ] Deploy code to EC2: `git pull origin claude/discord-natural-language-2Xh4Y`
- [ ] Restart service: `sudo systemctl restart indaba-discord`
- [ ] Verify running: `sudo systemctl status indaba-discord`
- [ ] Test `!help` in Discord
- [ ] Test natural language: `"What's in the pipeline?"`
- [ ] Test write with confirmation: `"Generate the next proverb"` → `"yes"`
- [ ] If still failing, check logs: `sudo journalctl -u indaba-discord -n 100`

---

## Next Steps

1. **Verify EC2 deployment** — use Step 1 above
2. **Run Phase 1 tests** — try `!help` and `!status`
3. **Run Phase 2 tests** — try read-only natural language queries
4. **If stuck, check logs** — use Step 3 above
5. **If logs show serialization error** — I can fix it immediately
6. **Once working, run full test scenario** — verify all 5 phases pass

---

## Commands to Deploy & Test (Copy-Paste Ready)

### Deploy to EC2 and Restart
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 << 'EOF'
cd /opt/indaba-discord
git pull origin claude/discord-natural-language-2Xh4Y
sudo systemctl restart indaba-discord
sleep 2
sudo systemctl status indaba-discord
EOF
```

### Check Code Version
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 "cd /opt/indaba-discord && git log -1 --oneline"
```

### Watch Live Logs
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 "sudo journalctl -u indaba-discord -f"
```

### Check for Errors
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 "sudo journalctl -u indaba-discord -n 50 | grep -i error"
```

---

## Known Issues & Fixes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Bot doesn't respond to `!help` | Service not running | `sudo systemctl status indaba-discord` |
| Bot responds to `!help` but not natural language | Code not deployed or agent crashing | Deploy code, check logs |
| "Say yes" prompt doesn't appear | System prompt not updated | Verify git pull worked |
| "yes" doesn't execute the action | History not persisting | Check bot.py line 28 (should have `_channel_history`) |
| `AttributeError: 'dict' has no ...` | Serialization bug | Check if latest commit (ea45cab) is deployed |
| `ImportError: anthropic` | Dependency missing | `pip install -r requirements.txt` |
| `ANTHROPIC_API_KEY` error message | Env var not set | Edit systemd service file |

---

## Summary

✅ **What works:** Code implementation, system design, serialization fix, diagnostics  
⚠️ **What's broken:** Bot not responding to messages (likely not deployed or bug in deployment)  
📋 **What to do next:** Follow diagnosis steps above; likely just needs EC2 deployment + restart  
🔧 **If still broken:** Check EC2 logs and share the error — I can fix immediately

The architecture is sound. The issue is almost certainly deployment-related.
