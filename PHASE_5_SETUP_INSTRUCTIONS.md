# Phase 5 Setup — Claude on the Web

**Objective:** Test Discord bot end-to-end functionality using Haiku model on claude.ai/code  
**Date:** 2026-04-27  
**Next Session Focus:** Testing (Haiku), then debugging (Sonnet)

---

## 📱 STEP 1: Launch Claude Code on the Web

### Instructions

1. Open your browser: **https://claude.ai/code**
2. Sign in with your Anthropic account
3. Click **"New session"** (or click **"+"**)
4. Fill in the form:
   - **Session name:** `indaba-discord-testing-haiku`
   - **Working directory:** `/Users/fidelnamisi/Indaba`
   - **Model:** Haiku 4.5
   - **Permissions:** Toggle to **OFF** (do NOT accept all permissions automatically)
5. Click **Create**

---

## 📋 STEP 2: Copy & Paste the Initialization Prompt

Once the session opens, **copy the entire text block below** and paste it into the chat:

---

### 🔷 COPY EVERYTHING FROM HERE TO THE END OF THIS SECTION 🔷

```
# PHASE 5 — Discord Bot Testing via Haiku

**Objective:** Test all Discord bot functionalities end-to-end. Document which workflows pass/fail.

**Important:** This is a TEST session using Haiku. Your job is to:
1. Understand the Discord bot implementation
2. Identify all Discord commands
3. Test each command's workflow
4. Document: ✅ WORKS or ❌ BROKEN + why
5. Save results to /Users/fidelnamisi/Indaba/PHASE_5_DISCORD_BOT_TEST_RESULTS.md

**You are NOT fixing bugs** — just documenting them for Sonnet to fix next session.

---

## Your First Task: Understand the Setup

Read these files to understand the current Discord bot state:

1. **Memory file:** `/Users/fidelnamisi/.claude/projects/-Users-fidelnamisi-Indaba/memory/project_discord_bot.md`
   - Current status: bot deployed on EC2, awaiting activation
   - Architecture: EC2 `/opt/indaba-discord` calls Indaba API at `localhost:5050`

2. **Phase 5 plan:** `/Users/fidelnamisi/Indaba/PHASE_5_DISCORD_BOT_TESTING.md`
   - What to test, how to structure findings

3. **Indaba-ops repo:** `/Users/fidelnamisi/Indaba-ops/indaba-bot/`
   - Explore the Discord bot code structure
   - Find all command handlers (search for `@bot.command`, `@bot.event`, etc.)

---

## Your Testing Workflow

For each Discord command found, document:

```
### Command: /[command_name]
- **What it does:** [brief description]
- **Workflow steps:** 
  1. User invokes in Discord
  2. Bot receives message
  3. Bot calls API endpoint (which one?)
  4. Data returned/stored/scheduled
  5. Result posted to Discord
- **Dependencies:** [what it needs: API endpoints, data files, env vars]
- **Status:** ✅ WORKS / ❌ BROKEN
- **Issue (if broken):** [specific error or blocker]
```

---

## Report Format

Save your results as `/Users/fidelnamisi/Indaba/PHASE_5_DISCORD_BOT_TEST_RESULTS.md`:

```markdown
# Phase 5 Discord Bot Testing Results
**Date:** [today's date]
**Tester:** Haiku via claude.ai/code
**Status:** Complete

## Commands Found
[List all Discord commands discovered]

## Detailed Testing Results

### Command: [name]
- Status: ✅ WORKS / ❌ BROKEN
- [details per template above]

[repeat for each command]

## Summary
- ✅ Passing workflows: [count]
- ❌ Failing workflows: [count]
- Fixes needed: [brief list]
```

---

## Key Files to Explore

- Discord bot code: `/Users/fidelnamisi/Indaba-ops/indaba-bot/` (if separate repo)
- Or in main Indaba repo: Search for `discord` in repo structure
- Look for: command definitions, event handlers, API calls
- Check: environment variables needed, API endpoints called, error handling

---

## When Complete

1. Save your test results file: `/Users/fidelnamisi/Indaba/PHASE_5_DISCORD_BOT_TEST_RESULTS.md`
2. Note any blocking issues in the report
3. Close the session (your work is saved to the results file)
4. The next session (Sonnet) will read your report and fix the issues

---

## Session Continuity

If you need to pause and come back:
- Session name: `indaba-discord-testing-haiku`
- Go to: claude.ai/code → Sessions → find the session → click to restore
- Pick up from exactly where you left off
```

### 🔷 END OF COPY-PASTE BLOCK 🔷

---

## Session Name for Later

If you need to resume later, your session is saved as:

```
indaba-discord-testing-haiku
```

Simply go to **claude.ai/code** → **Sessions** → find `indaba-discord-testing-haiku` → click to restore.

---

## What You're Testing

Based on prior work, the Discord bot should support:
- **Commands:** `/proverb`, `/chapter-teaser`, and any others found in the code
- **Workflows:** Each command should have an end-to-end path from Discord → Indaba API → result posted back

Your job: verify which ones work, which ones are broken, and why.

---

## After Testing Complete

Once you've documented all test results:

1. **Save the results file:** `/Users/fidelnamisi/Indaba/PHASE_5_DISCORD_BOT_TEST_RESULTS.md`
2. **Close the session** (Claude will prompt when done)
3. **Next session** (Sonnet) will read your report and fix issues

---

## Questions?

Refer back to:
- `PHASE_5_DISCORD_BOT_TESTING.md` — detailed testing plan
- `project_discord_bot.md` (memory) — current bot status
- `PHASE_4_HANDOFF.md` — infrastructure status (EC2 is live)
