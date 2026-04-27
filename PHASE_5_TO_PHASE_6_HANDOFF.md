# Phase 5 → Phase 6 Handoff: Discord Bot Configuration

**From:** Haiku (Phase 5 Testing)  
**To:** Sonnet (Phase 6 Fixes)  
**Date:** 2026-04-27

---

## What Haiku Found

Read the test results file first:
```
/home/user/indaba/PHASE_5_DISCORD_BOT_TEST_RESULTS.md
```

**TL;DR:** The Discord bot code is production-ready. It cannot run because two environment variables are missing/broken.

---

## Two Issues to Fix

### Issue 1: DISCORD_BOT_TOKEN (CRITICAL — Bot won't start)

**File to Edit:**
```
/home/user/indaba/discord_bot/indaba-discord.service
```

**Current (broken):**
```ini
Environment="DISCORD_BOT_TOKEN=PASTE_TOKEN_HERE"
```

**What to do:**

1. **Obtain a Discord bot token** (if not already available):
   - Go to Discord Developer Portal: https://discord.com/developers/applications
   - Create a new application or find existing "Indaba" app
   - Under "Bot" section, copy the bot token
   - Token format: `MzAxMjM0NTY3ODkwMTIzNDU2.CtQNtg.xyzABC...` (very long string)

2. **Update the service file** at `/home/user/indaba/discord_bot/indaba-discord.service`:
   ```ini
   Environment="DISCORD_BOT_TOKEN=YOUR_ACTUAL_TOKEN_HERE"
   ```
   Replace `YOUR_ACTUAL_TOKEN_HERE` with the actual token from Discord.

3. **Verify the change:**
   ```bash
   grep "DISCORD_BOT_TOKEN" /home/user/indaba/discord_bot/indaba-discord.service
   ```
   Should show the token (masked for security in real output, but must not say "PASTE_TOKEN_HERE")

4. **Copy the updated file to EC2:**
   ```bash
   scp -i ~/Indaba/ec2-key.pem /home/user/indaba/discord_bot/indaba-discord.service ubuntu@13.218.60.13:/opt/indaba-discord/indaba-discord.service
   ```

5. **Restart the bot service on EC2:**
   ```bash
   ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 'sudo systemctl daemon-reload && sudo systemctl restart indaba-discord'
   ```

6. **Verify bot is running:**
   ```bash
   ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 'sudo systemctl status indaba-discord'
   ```
   Should show: `active (running)`

---

### Issue 2: GITHUB_TOKEN (MEDIUM — !idea command won't push to GitHub)

**File to Edit:**
```
/home/user/indaba/discord_bot/indaba-discord.service
```

**Current (broken):**
```ini
Environment="GITHUB_TOKEN="
```

**What to do:**

1. **Obtain a GitHub personal access token** (if not already available):
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Create a new token with scopes: `repo` (full control of private repos)
   - Copy the token (format: `ghp_xxxxxxxxxxxx`)

2. **Update the service file** at `/home/user/indaba/discord_bot/indaba-discord.service`:
   ```ini
   Environment="GITHUB_TOKEN=YOUR_GITHUB_TOKEN_HERE"
   ```
   Replace `YOUR_GITHUB_TOKEN_HERE` with the actual token from GitHub.

3. **Verify the change:**
   ```bash
   grep "GITHUB_TOKEN" /home/user/indaba/discord_bot/indaba-discord.service
   ```
   Should show a token value (not empty)

4. **Copy the updated file to EC2:**
   ```bash
   scp -i ~/Indaba/ec2-key.pem /home/user/indaba/discord_bot/indaba-discord.service ubuntu@13.218.60.13:/opt/indaba-discord/indaba-discord.service
   ```

5. **Restart the bot service on EC2:**
   ```bash
   ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 'sudo systemctl daemon-reload && sudo systemctl restart indaba-discord'
   ```

---

## Testing Checklist

Once both tokens are configured, test the bot:

### Quick Startup Test
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
sudo systemctl status indaba-discord
tail -f /var/log/syslog | grep indaba-discord
```

Should see: `[Indaba Bot] Connected as YourBotName#0000 | Listening in #indaba-ops`

### Discord Channel Test
In your Discord server's #indaba-ops channel, type:
```
!help
```

Bot should reply with command list.

### Full Command Test (one from each category)
```
!hub                           # Pipeline overview
!pipeline                      # List all entries
!works                         # List book series
!idea Test bot is working      # Add idea to ROADMAP (tests GITHUB_TOKEN)
```

### Natural Language Test
```
Show me all Love Back chapters in producing
```

Bot should use Claude agent to call `pipeline_list("LB", "producing")` and return results.

---

## Files Involved

| File | Purpose | Status |
|------|---------|--------|
| `/home/user/indaba/PHASE_5_DISCORD_BOT_TEST_RESULTS.md` | Full test results (read first) | ✅ Complete |
| `/home/user/indaba/discord_bot/bot.py` | Main bot code | ✅ No changes needed |
| `/home/user/indaba/discord_bot/claude_agent.py` | Agent tools | ✅ No changes needed |
| `/home/user/indaba/discord_bot/indaba_client.py` | API client | ✅ No changes needed |
| `/home/user/indaba/discord_bot/indaba-discord.service` | Service file with env vars | ❌ **NEEDS TOKENS** |
| `/opt/indaba-discord/indaba-discord.service` | Service file on EC2 | ❌ **NEEDS TOKENS** |

---

## What NOT to Do

- ❌ Do NOT commit Discord or GitHub tokens to git
- ❌ Do NOT commit the service file with real tokens
- ❌ Do NOT modify bot.py, claude_agent.py, or indaba_client.py (they're correct)
- ❌ Do NOT change the INDABA_BASE_URL or other config values

---

## Success Criteria

- ✅ Bot starts and announces in Discord: "Indaba Bot online. Type `!help` for commands."
- ✅ `!help` command returns the help list
- ✅ `!hub` command returns pipeline summary
- ✅ `!idea` command adds to ROADMAP.md AND pushes to GitHub
- ✅ Natural language requests work (Claude agent picks right tools)
- ✅ No errors in bot logs (`sudo systemctl status indaba-discord`)

---

## Questions for Fidel (if stuck)

- Do you have the Discord bot token from the Developer Portal?
- Do you have a GitHub personal access token for git push?
- Are you the server admin in the Discord server where the bot will run?
- Is the EC2 instance still running and accessible at 13.218.60.13?

---

## After Tokens Are Set

1. Update EC2 service file with tokens
2. Restart bot service
3. Verify in Discord (#indaba-ops channel)
4. Run quick tests (see Testing Checklist above)
5. Commit the PHASE_5_DISCORD_BOT_TEST_RESULTS.md file to main (already done)
6. Document any new issues found in Phase 6 handoff

