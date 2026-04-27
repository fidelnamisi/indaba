# Phase 5 Setup — Claude on the Web

**Objective:** Test Discord bot end-to-end functionality using Haiku model on claude.ai/code  
**Date:** 2026-04-27  
**Source of Truth:** GitHub repo (fidelnamisi/indaba) — no local filesystem  
**Next Session Focus:** Testing (Haiku), then debugging (Sonnet)

---

## 📱 STEP 1: Launch Claude Code on the Web

### Instructions

1. Open your browser: **https://claude.ai/code**
2. Sign in with your Anthropic account
3. Click **"New session"** (or click **"+"**)
4. Fill in the form:
   - **Session name:** `indaba-discord-testing-haiku`
   - **Repository:** GitHub — `fidelnamisi/indaba`
   - **Model:** Haiku 4.5
   - **Permissions:** Toggle to **OFF** (do NOT accept all permissions automatically)
5. Click **Create**

---

## 📋 STEP 2: Copy & Paste the Initialization Prompt

Once the session opens and you're in the GitHub repo, **copy the entire text block below** and paste it into the chat:

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

Read these files from the GitHub repo to understand the current Discord bot state:

1. **This repo:** fidelnamisi/indaba (GitHub)
   - Read: `PHASE_5_DISCORD_BOT_TESTING.md` — what to test, how to structure findings
   - Read: `PHASE_4_HANDOFF.md` — infrastructure status (EC2 live, data in sync)

2. **Discord bot code:** Separate GitHub repo — `fidelnamisi/indaba-ops`
   - Directory: `indaba-bot/`
   - Explore the Discord bot code structure
   - Find all command handlers (search for `@bot.command`, `@bot.event`, etc.)
   - Look for: command definitions, event handlers, API calls to Indaba
   - Check: environment variables needed, error handling

3. **Discord bot status:**
   - Current: Deployed on EC2 at `/opt/indaba-discord`
   - Architecture: Bot calls Indaba API at `https://indaba.realmsandroads.com` (EC2 production URL)
   - Awaiting: `DISCORD_BOT_TOKEN` env var to activate

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

Create a new file in the GitHub repo: `PHASE_5_DISCORD_BOT_TEST_RESULTS.md`:

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

## When Complete

1. Create the test results file: `PHASE_5_DISCORD_BOT_TEST_RESULTS.md`
2. Note any blocking issues in the report
3. **Commit to GitHub:** `git add PHASE_5_DISCORD_BOT_TEST_RESULTS.md && git commit -m "Phase 5 testing results: Discord bot workflows tested and documented"`
4. **Push to GitHub:** `git push origin main`
5. Close the session
6. The next session (Sonnet) will read your results from GitHub and fix the issues

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
