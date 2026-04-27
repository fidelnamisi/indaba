# Phase 6 Handoff: Natural Language Discord Bot

**From:** Sonnet (Phase 5 fixes + Phase 6 design)
**To:** Sonnet (Phase 6 implementation)
**Date:** 2026-04-27
**Branch:** `claude/discord-testing-setup-3qaol`

---

## What Was Done in Phase 5 + This Session

- ✅ Discord bot token and GitHub token configured on EC2 — bot is **live**
- ✅ SAST (GMT+2) timezone fixed in `roadmap.py`
- ✅ `discord_bot/indaba-discord.service` added to `.gitignore` (tokens never committed)
- ✅ `!preview`, `!generate`, `!queue` commands added — but then Fidel rejected this approach
- ❌ Explicit commands for content operations are confusing and wrong
  - `!generate` sounds generic but only works for proverbs
  - `!queue` is cryptic
  - The whole explicit-command paradigm is the wrong UX

---

## The Problem with Current Commands

The bot has 12+ explicit `!` commands. Most are fine for quick reads (`!hub`, `!status`).  
But **content operations** (generate proverb, queue post, publish chapter, etc.) are now handled with confusing explicit commands like `!generate` and `!queue <id>`.

Fidel's actual mental model is:

> "Generate the next proverb. Show it to me. If I like it, queue it."

Not:
> "!preview → read the ID → !generate abc-123 → read the ID again → !queue abc-123"

---

## The Vision: Natural Language Primary

**Everything Fidel says in plain English. The bot handles it.**

Example flows that must work:

```
Fidel: "Generate the next proverb"
Bot:   Shows the proverb text and caption preview
Bot:   "Ready to queue. Say 'yes' to schedule it."

Fidel: "Yes"
Bot:   "Done. Queued for Tuesday 29 April 16:00 SAST."
```

```
Fidel: "Publish chapter 3 of Love Back to the website"
Bot:   "Ready to publish 'love-back-ch3-pipeline' to realmsandroads.com/love-back/ch3. Say 'yes' to confirm."

Fidel: "Go ahead"
Bot:   "Published. https://realmsandroads.com/love-back/ch3"
```

```
Fidel: "What's in the pipeline?"
Bot:   Returns pipeline summary immediately (no confirmation needed — read-only)
```

---

## Architecture for Next Session

### Key Insight: The Agent Needs Memory Per Channel

Currently `run_agent()` in `claude_agent.py` starts fresh every message. This means:
- Bot generates proverb preview
- User says "yes"
- Bot has no idea what "yes" refers to

**Fix:** Maintain a per-channel conversation history so the agent remembers context across turns.

### Two Categories of Operations

| Category | Behaviour |
|----------|-----------|
| **Read** (hub, pipeline, works, status) | Execute immediately, return result |
| **Write** (generate, queue, publish, deploy, stage) | Preview first, wait for confirmation, then execute |

### What to Build

**1. Per-channel conversation history (`bot.py`)**
```python
# At module level
_channel_history: dict[int, list] = {}  # channel_id → messages list
```

Pass the channel's history into `run_agent()` on every call, and update it with the response. Cap at last 10 turns to avoid token bloat.

**2. Updated `run_agent()` signature (`claude_agent.py`)**
```python
def run_agent(user_message: str, history: list, progress_callback=None) -> tuple[str, list]:
    # Returns (response_text, updated_history)
```

**3. Updated system prompt (`claude_agent.py`)**

The system prompt must instruct Claude to:
- For **write operations**: describe what it's about to do and explicitly ask "Say 'yes' to confirm or 'skip' to cancel" — do NOT execute yet
- For **read operations**: execute immediately, no confirmation needed
- When user says "yes" / "go" / "do it" / "looks good" / "queue it" / "ship it" / "confirm" / "ok go": execute the pending action
- When user says "no" / "skip" / "cancel" / "different one": cancel and offer alternatives

**4. Remove confusing commands**

Delete from `bot.py`:
- `!preview` (replaced by natural language)
- `!generate` (replaced by natural language)
- `!queue` (replaced by natural language)

Keep these `!` shortcuts (they're fast and read-only):
- `!help` — command list
- `!hub` — pipeline overview
- `!works` — list series
- `!status` — EC2 sender health
- `!pipeline [book] [stage]` — filtered pipeline list

Optionally keep these write shortcuts (they're single-step, no preview needed):
- `!stage <id> <stage>` — quick stage move
- `!idea <text>` — quick idea capture

---

## Files to Modify

| File | What to change |
|------|---------------|
| `discord_bot/bot.py` | Add `_channel_history` dict; pass history into `run_agent`; update history after each response; remove `!preview`, `!generate`, `!queue` |
| `discord_bot/claude_agent.py` | Update `run_agent()` to accept and return history; overhaul system prompt with confirmation pattern |
| `discord_bot/indaba_client.py` | No changes needed |

---

## Test Scenarios for Next Session

Once implemented, verify these work end-to-end in Discord:

### Read (no confirmation needed)
- "What's in the pipeline?" → immediate response
- "List all Love Back chapters in producing" → immediate response
- "Show me the promo queue status" → immediate response

### Write (must show preview + ask to confirm)
- "Generate the next proverb" → shows caption preview → "yes" → queued
- "Publish chapter 3 of Love Back" → shows what it would publish → "yes" → published
- "Move love-back-ch3-pipeline to publishing" → confirms the move → "yes" → moved

### Cancellation
- "Generate a proverb" → preview shown → "no, skip it" → bot cancels and offers to show another

### Multi-step
- "Generate 2 proverbs and queue them" → bot previews first, asks confirm, executes, previews second, asks confirm, executes

---

## Current Bot Status on EC2

- **Service:** `indaba-discord` — running at `/opt/indaba-discord`
- **Tokens:** Set directly in EC2 service file (not in git)
- **Branch:** `claude/discord-testing-setup-3qaol` — pull this on EC2 after changes
- **Deploy command:**
  ```bash
  ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
  cd /opt/indaba-discord && git pull && sudo systemctl restart indaba-discord
  ```

---

## What NOT to Do

- ❌ Do not add more `!` commands for content operations
- ❌ Do not commit `discord_bot/indaba-discord.service` (it has real tokens, it's gitignored)
- ❌ Do not change `indaba_client.py` — the API client is complete and correct
- ❌ Do not change any Flask routes in `app.py` — the backend API is stable
