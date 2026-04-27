# Phase 5 — Discord Bot Testing & Debug
**Date:** 2026-04-27  
**Objective:** Test all Discord bot functionalities end-to-end via Claude on the web (Haiku model)  
**Platform:** claude.ai/code web interface

---

## Session Overview

This session uses **Haiku (lower model)** running on Claude.ai/code (web) to:
1. Test all Discord bot commands that have been set up
2. Document which workflows work end-to-end
3. Identify bugs, blockers, and issues
4. Report back with test results for **Sonnet (higher model)** to fix in the next session

**Session Name:** `indaba-discord-testing-haiku`

---

## Setup Instructions

### Step 1: Launch Claude Code on the Web

1. Open browser: **https://claude.ai/code**
2. Sign in with your Anthropic account
3. Click **"New session"** (or **"+"** at top)
4. **Session name:** Type exactly: `indaba-discord-testing-haiku`
5. **Repository:** GitHub — `fidelnamisi/indaba`
6. **Permissions:** Toggle to **OFF** (accept all permissions disabled)
7. **Model:** Select **Haiku 4.5**
8. Click **Create**

### Step 2: Paste the Initialization Prompt

Once the session loads, copy and paste the entire text block below into the chat:

---

## 🔷 COPY & PASTE THIS PROMPT INTO CLAUDE.AI/CODE 🔷

```
# PHASE 5 — Discord Bot Testing via Haiku (claude.ai/code)

You are testing the Indaba Discord bot's end-to-end functionality. Your job:
1. Read the Discord bot documentation and recent code changes
2. Identify all Discord commands that have been implemented
3. Test each command's workflow (what it does, what APIs it calls)
4. Document which workflows work, which fail, and why
5. Report back with: ✅ passing workflows, ❌ failing workflows, and fixes needed

**Important:** This is a TEST SESSION using Haiku. You're NOT fixing bugs—just documenting them. Sonnet will fix them next session.

**Your first task:** Read these files to understand the Discord bot setup:

1. /Users/fidelnamisi/.claude/projects/-Users-fidelnamisi-Indaba/memory/project_discord_bot.md
   - Current Discord bot status
   
2. Read /Users/fidelnamisi/Indaba-ops/indaba-bot/ directory structure
   - What files exist, what's implemented
   
3. Read the Discord bot main file and identify all command handlers

Then:
- List all Discord commands found
- For each command, trace the workflow (what it calls, what data it needs)
- Document any dependencies or requirements
- Test (simulate) each workflow and report: ✅ works or ❌ broken + why

Report format:
```
## Discord Bot Testing Results

### Command: /proverb
- **What it does:** [description]
- **Workflow:** [steps it takes]
- **Dependencies:** [what it needs]
- **Status:** ✅ WORKS / ❌ BROKEN
- **Issue (if broken):** [specific error or blocker]

[repeat for each command]

## Summary
✅ Passing workflows: [count]
❌ Broken workflows: [count] + brief fixes needed
```

**Git repo note:** Indaba-ops is a separate repo at ~/Indaba-ops. You may need to cd there to explore. Report the full state.
```

---

## Important Notes

- **Do NOT fix bugs** — document them for Sonnet
- **Do NOT commit changes** — this is testing only
- **Do update memory** if you discover new information about the Discord bot setup
- **Report comprehensively** — Sonnet will use your report to know what to fix

---

## After Testing Complete

Once you've documented all workflows:

1. Create file: `PHASE_5_DISCORD_BOT_TEST_RESULTS.md` in the GitHub repo
2. Commit: `git add PHASE_5_DISCORD_BOT_TEST_RESULTS.md && git commit -m "Phase 5 testing results: Discord bot workflows tested"`
3. Push: `git push origin main`
4. Close the session
5. Results are now saved to GitHub (single source of truth)

---

## Session Continuity

If you need to **pause and come back later:**
- Your session is saved at: `indaba-discord-testing-haiku`
- To resume: claude.ai/code → Sessions → find `indaba-discord-testing-haiku` → click to restore
- Pick up from exactly where you left off

---

## What to Test

Based on prior work, the Discord bot should support these workflows (find and test):
- `/proverb` — generate/schedule proverb posts
- `/chapter-teaser` — create chapter teasers
- Any other commands defined in the bot code

Test each command's **end-to-end workflow:**
1. User invokes command in Discord
2. Bot receives message
3. Bot calls Indaba API (or local function)
4. Data is returned / stored / scheduled
5. Result posted back to Discord

Document each step and any failures.
