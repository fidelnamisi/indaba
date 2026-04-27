# Phase 6 Implementation Report

**Date:** 2026-04-27  
**Branch:** `claude/discord-natural-language-2Xh4Y`  
**Commits:** 2

---

## Changes Made

### Commit 1: Phase 6 Natural Language Architecture

**Files Modified:**
- `discord_bot/bot.py`
- `discord_bot/claude_agent.py`

#### `claude_agent.py` Changes

**System Prompt Overhaul:**
- New section: "Conversation memory" — instructs agent to use history for context across turns
- New section: "Two types of operations"
  - **Read ops** execute immediately (hub, pipeline, works, status, etc.)
  - **Write ops** preview first, then ask "Say 'yes' to confirm or 'no' to cancel"
- Added explicit affirmation keywords: "yes", "go ahead", "do it", "ok", "confirm", "queue it", "ship it", "looks good"
- Added explicit cancellation keywords: "no", "skip", "cancel", "different one"
- Added list of all write operations requiring confirmation

**`run_agent()` Function Signature Change:**
```python
# Before
def run_agent(user_message: str, progress_callback=None) -> str:

# After
def run_agent(user_message: str, history: list = None, progress_callback=None) -> tuple:
```

**History Management:**
- Accepts `history: list` parameter (prior conversation messages)
- Returns `tuple` of `(response_text, updated_history)`
- History is capped at last 30 messages to manage token usage
- History is built as: `messages = list(history or []) + [new user message]`

**Critical Fix (Commit 2):**
Added helpers to convert SDK objects to plain dicts for history storage:
```python
def _content_block_to_dict(block) -> dict:
    # Converts TextBlock, ToolUseBlock to {"type": "text", "text": ...} format

def _content_to_dict(content) -> list | dict:
    # Converts list of SDK blocks to list of dicts
```

This was **essential** because:
- `response.content` from the Anthropic SDK contains SDK objects
- These objects can't be serialized/stored in the `_channel_history` dict
- On the next turn, when history is passed back to the API, it must be plain dicts
- The API expects `{"type": "text", "text": "..."}` format, not SDK objects

#### `bot.py` Changes

**Per-Channel History Dict (Module Level):**
```python
_channel_history: dict[int, list] = {}
```
Maps `channel_id` → list of message dicts. Persists across messages in the same channel.

**Updated `_handle_natural_language()`:**
1. Gets channel history: `history = _channel_history.get(channel_id, [])`
2. Calls agent with history: `result, updated_history = await run_agent(..., history, ...)`
3. Saves updated history: `_channel_history[channel_id] = updated_history`

**Updated `!help` Command:**
- Repositioned natural language as primary interface
- Highlighted that write operations show preview + confirmation
- Reduced command list to show only important shortcuts

---

## Expected Behavior After Implementation

### Read-Only Operations (No Confirmation)

User sends: `"What's in the pipeline?"`

1. `_handle_natural_language()` called
2. history = [] (first message in channel)
3. Agent runs with empty history
4. Agent calls `pipeline_list()` tool immediately
5. Agent returns result directly (no confirmation needed)
6. Bot replies with pipeline

```
User: "What's in the pipeline?"
Bot: "**Pipeline** (15 entries)
[LB] Glass Hearts — *producing* `lb-glass-hearts-ch1`
...
"
```

### Write Operations (With Confirmation)

User sends: `"Generate the next proverb"`

#### Turn 1: Preview
1. history = [] 
2. Agent calls `promo_broadcast_list()` to get next unfinished proverb
3. Agent calls `promo_broadcast_generate(proverb_id)` to generate caption + image
4. Agent **does NOT call** `promo_broadcast_queue()` yet
5. Agent returns preview text ending with **"Say 'yes' to confirm or 'no' to cancel."**
6. messages = [
   - {"role": "user", "content": "Generate the next proverb"},
   - {"role": "assistant", "content": [tool calls...]} ,
   - {"role": "user", "content": [tool results...]},
   - {"role": "assistant", "content": [{"type": "text", "text": "Here's the preview..."}]}
  ]
7. `_channel_history[channel_id]` = messages
8. Bot replies with preview

```
User: "Generate the next proverb"
Bot: "**Preview - Proverb Broadcast**
...
Say 'yes' to confirm or 'no' to cancel."
```

#### Turn 2: Confirmation
1. history = [prior messages from Turn 1, now with full tool context]
2. User sends: "yes"
3. messages = history + [{"role": "user", "content": "yes"}]
4. Agent reads history, sees it was generating a proverb, sees the proverb_id from tool results
5. Agent calls `promo_broadcast_queue(proverb_id)`
6. Agent returns confirmation

```
User: "yes"
Bot: "Done. Queued for Tuesday 29 April 16:00 SAST."
```

---

## Critical Assumptions & Constraints

### Assumption 1: History Survives Across Turns
- `_channel_history` dict persists in memory for the lifetime of the bot process
- If bot restarts, all channel histories are lost (fresh state)
- This is intentional — history is per-bot-session, not persistent across restarts

### Assumption 2: Agent Remembers Implied Context
- When user says "yes" in Turn 2, the agent needs to read the history and understand what action is pending
- The system prompt instructs the agent to "execute whatever write action you last previewed"
- This requires the agent to parse the history and identify:
  - What tools were called in previous turns
  - What the results were
  - What action was "previewed"
- **Risk:** If the agent doesn't have good context understanding, it might fail to match "yes" with the right action

### Assumption 3: Tool Results Contain Enough Info
- When `promo_broadcast_generate(proverb_id)` returns, the result includes the generated caption/image
- When user says "yes", the agent can queue the same proverb without re-fetching it
- **Risk:** If tool results are incomplete, agent might not have the info needed to execute

### Assumption 4: Anthropic API Accepts Dict Messages
- The agent passes `messages` list with mixed dicts (converted from SDK objects) back to the API
- The API must accept this format and handle tool_use blocks in dict format
- **Risk (Low):** The Anthropic SDK is designed to handle both dict and object formats

---

## Known Limitations & Edge Cases

### 1. History Token Bloat
- History is capped at 30 messages, but each tool call adds 2-3 messages
- Long multi-step operations might exceed token limits
- **Mitigation:** Cap is 30 messages, which is ~10 conversational turns

### 2. Lost History on Restart
- Bot restart clears all channel histories
- User loses context if they were mid-confirmation
- **Acceptable:** Rare event, users can simply retry

### 3. Ambiguous Affirmations
- User says "yes, but..." — agent might not catch the "but"
- User says "yes" hours later — agent history is gone if bot restarted
- **Mitigation:** System prompt covers common affirmation/cancellation phrases

### 4. Multi-Step Operations
- User: "Generate 3 proverbs and queue them"
- Agent should loop: preview 1 → ask confirm → execute → preview 2 → ask confirm → execute → ...
- **Current:** This might fail if agent doesn't understand the loop pattern
- **Mitigation:** System prompt says "for multi-step tasks, plan the steps, execute sequentially"

### 5. Tool Order Dependency
- Some operations must happen in order (e.g., generate before queue)
- Agent must infer this from the tools available and context
- **Current:** Relies on agent understanding of dependencies

---

## Troubleshooting: Most Likely Failures

### Symptom: Bot responds to `!commands` but not natural language

**Cause:** `_handle_natural_language()` is crashing due to an exception

**Debug:**
1. Check EC2 logs: `sudo journalctl -u indaba-discord -n 50`
2. Look for errors like:
   - `AttributeError: 'dict' object has no attribute ...` (SDK object mismatch)
   - `TypeError: run_agent() missing required argument` (signature mismatch)
   - `KeyError: 'channel'` (missing field in dict)

### Symptom: Agent says "ANTHROPIC_API_KEY not set"

**Cause:** Environment variable not set or not reloaded after restart

**Fix:**
```bash
sudo nano /etc/systemd/system/indaba-discord.service
# Check that Environment="ANTHROPIC_API_KEY=..." is set
sudo systemctl daemon-reload
sudo systemctl restart indaba-discord
```

### Symptom: Agent doesn't show "Say yes to confirm" prompt

**Cause:** System prompt change didn't take effect

**Debug:**
1. Verify bot pulled the latest code: `git log -1` on EC2
2. Verify service was restarted: `sudo systemctl status indaba-discord`
3. Check system prompt is in the running code: add a debug log line

### Symptom: Agent shows preview, but "yes" doesn't queue

**Cause:** History not persisting, or agent doesn't understand context

**Debug:**
1. Check that `_channel_history` is updating: add print statement
2. Check that history is passed correctly: verify function signature
3. Check agent can read history: add "Debugging" to the preview message showing what it remembers

---

## Testing Checklist

### Phase 1: Infrastructure
- [ ] Bot service is running on EC2
- [ ] DISCORD_BOT_TOKEN is set and valid
- [ ] ANTHROPIC_API_KEY is set and valid
- [ ] Bot is online in Discord (check member list)
- [ ] Bot is in #indaba-ops channel

### Phase 2: Read-Only Baseline
- [ ] `!help` works
- [ ] `!status` works  
- [ ] `!hub` works
- [ ] `"What's in the pipeline?"` returns result immediately

### Phase 3: Write Operations
- [ ] `"Generate the next proverb"` → shows preview ending with "Say yes"
- [ ] `"yes"` → proverb is queued, bot confirms
- [ ] `"Generate a proverb"` → preview → `"no"` → cancelled, no action
- [ ] `"Publish Love Back chapter 3"` → shows what would be published → `"yes"` → published

### Phase 4: Multi-Turn Memory
- [ ] Send message, agent responds
- [ ] Send related follow-up, agent remembers context from previous turn
- [ ] Send same request hours later (after restart) → fresh history, works correctly

### Phase 5: Edge Cases
- [ ] Empty message → agent handles gracefully
- [ ] Very long message → agent truncates/processes
- [ ] Special characters in message → agent handles
- [ ] Rapid messages → agent queues or processes in order
