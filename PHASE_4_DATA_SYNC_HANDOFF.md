# Phase 4 Data Sync Handoff — Outstanding Issues

**Date:** 2026-04-27  
**Session:** Haiku (Data Sync)  
**Status:** Data files copied to EC2, 2 critical issues remain

---

## Session Accomplishments

✅ Copied 20 data files from localhost to EC2 (13 missing + 7 truncated)  
✅ Verified EC2 has all files: `ls /opt/indaba-app/data/ | wc -l` → 35 files  
✅ Hub summary pipeline counts match: 62 producing, 6 promoting, 6 publishing  
✅ Service running on port 5050 (after killing old processes)

---

## Pending Issues to Resolve

### Issue #1: Messages Queue Discrepancy (HIGH PRIORITY)

**Symptom:**
```
LOCALHOST: messages_queued = 22
EC2:       messages_queued = 14
```

**Root Cause:** Unknown. File is correct when copied (MD5: b4cdd4e36f1287e907fae636d3637bc8, 22 queued messages), but when app reads it, only 14 are counted as queued.

**Investigation Steps:**
1. Check if `sync_existing_data_to_assets()` in `utils/migrate.py` is filtering or modifying promo_messages.json
2. Search for any code that runs on app startup and writes to promo_messages.json
3. Check for .git post-merge hooks that might reset the file
4. Verify MD5 of EC2 file after app startup

**Files to Check:**
- `utils/migrate.py` — line ~50 onwards, especially `sync_existing_data_to_assets()`
- `routes/promo_messages.py` — any initialization code
- Look for writes to promo_messages.json: `grep -r "promo_messages.json" . --include="*.py" | grep -E "write|dump|replace"`

**Expected Outcome:**
EC2 hub summary should show `messages_queued: 22` (matching localhost)

---

### Issue #2: Port Race Condition on Service Restart

**Symptom:**
When `systemctl restart indaba-app` is called, if the old process hasn't fully released port 5050, the new process binds to 5051 instead. This breaks nginx routing (which expects port 5050).

**Root Cause:**
App startup uses `find_free_port(5050, max_tries=20)` which increments to 5051 if 5050 is busy.
GitHub Actions auto-deploy doesn't kill the old process before restarting.

**Fix:** Harden `.github/workflows/deploy.yml` to ensure old process is killed first.

**Current workflow file location:** `.github/workflows/deploy.yml`

**Required Change:**
Before `systemctl restart indaba-app`, add:
```bash
sudo pkill -9 -f 'python.*app.py' || true
sudo lsof -i :5050 -S -t | xargs -r kill -9 || true
sudo lsof -i :5051 -S -t | xargs -r kill -9 || true
sleep 2
```

**Files to Modify:**
- `.github/workflows/deploy.yml` — add kill commands before restart

**Expected Outcome:**
Deploy restarts always bind to port 5050, nginx proxies work correctly

---

## Instructions for Next Session

### Step 1: Investigate Messages Queue Discrepancy

**Run these commands to diagnose:**

```bash
cd ~/Indaba

# Check local file
echo "=== LOCAL FILE ==="
md5 data/promo_messages.json
python3 -c "
import json
with open('data/promo_messages.json') as f:
    data = json.load(f)
queued = sum(1 for m in data['messages'] if m.get('status') == 'queued')
print(f'Local queued: {queued}')
"

# Check EC2 file
echo ""
echo "=== EC2 FILE AFTER STARTUP ==="
ssh -i ec2-key.pem ubuntu@13.218.60.13 "
md5sum /opt/indaba-app/data/promo_messages.json
python3 -c \"
import json
with open('/opt/indaba-app/data/promo_messages.json') as f:
    data = json.load(f)
queued = sum(1 for m in data['messages'] if m.get('status') == 'queued')
print(f'EC2 queued: {queued}')
\"
"

# Check app logs for any file writes
echo ""
echo "=== APP LOGS (search for promo_messages activity) ==="
ssh -i ec2-key.pem ubuntu@13.218.60.13 "
sudo journalctl -u indaba-app -n 50 --no-pager | grep -i 'promo\|message\|sync' || echo 'No matches in logs'
"
```

**If files match but API shows different count:**
- Search codebase for code that writes to promo_messages.json:
  ```bash
  grep -r "promo_messages" routes/ utils/ --include="*.py" | grep -v "#" | grep -E "write|dump|replace|json.dumps"
  ```
- Check `utils/migrate.py` line ~50 for `sync_existing_data_to_assets()` function
- Look for any filtering logic in `routes/promo_messages.py`

**If EC2 file is different from local:**
- Check git history: `cd /opt/indaba-app && git log --oneline -10 -- data/promo_messages.json`
- Check for post-merge hooks: `cd /opt/indaba-app && find . -name 'post-merge' -o -name 'post-checkout'`
- Verify file permissions: `stat /opt/indaba-app/data/promo_messages.json | grep -E "Uid|Gid"`

### Step 2: Fix GitHub Actions Deploy (Port Race Condition)

**Read current deploy workflow:**
```bash
cat .github/workflows/deploy.yml
```

**Update the deploy workflow to kill old processes:**

Find the section that restarts the service (should look like):
```yaml
- name: Restart Indaba App
  run: |
    ssh -i ~/ec2-key.pem ubuntu@13.218.60.13 'sudo systemctl restart indaba-app'
```

Replace with:
```yaml
- name: Restart Indaba App
  run: |
    ssh -i ~/ec2-key.pem ubuntu@13.218.60.13 '
      sudo pkill -9 -f "python.*app.py" || true
      sudo lsof -i :5050 -S -t | xargs -r kill -9 || true
      sudo lsof -i :5051 -S -t | xargs -r kill -9 || true
      sleep 2
      sudo systemctl restart indaba-app
    '
```

**After editing, test with a push:**
```bash
git add .github/workflows/deploy.yml
git commit -m "Harden deploy: kill old processes before restart (Phase 4 fix)"
git push origin main
# Monitor EC2 logs: sudo journalctl -u indaba-app -f
```

### Step 3: Verify Both Issues Are Resolved

**After fixes, run final validation:**

```bash
echo "=== HUB SUMMARY COMPARISON ==="
echo ""
echo "LOCALHOST:"
curl -s http://localhost:5050/api/hub/summary | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'  Pipeline: {data[\"pipeline\"]}')
print(f'  Messages queued: {data[\"promote\"][\"messages_queued\"]}')
"

echo ""
echo "EC2:"
curl -s https://indaba.realmsandroads.com/api/hub/summary | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'  Pipeline: {data[\"pipeline\"]}')
print(f'  Messages queued: {data[\"promote\"][\"messages_queued\"]}')
"

echo ""
echo "✅ If both show messages_queued=22 and pipeline counts match, Phase 4 is COMPLETE"
```

---

## Files Modified in This Session

- **Copied to EC2:** 20 files
- **Modified:** None (investigation only)

## Files to Modify in Next Session

- `.github/workflows/deploy.yml` — add process kill commands

---

## Critical Context

**EC2 Connection:**
```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13
EC2 IP: 13.218.60.13
EC2 App Port: 5050 (via nginx HTTPS: indaba.realmsandroads.com)
App Location: /opt/indaba-app
Data Location: /opt/indaba-app/data
Service Name: indaba-app
```

**Known Good File Checksums:**
```
Local promo_messages.json:  b4cdd4e36f1287e907fae636d3637bc8 (98337 bytes, 22 queued)
Local content_pipeline.json: [check with: md5 ~/Indaba/data/content_pipeline.json]
```

**Port Status:**
- Port 5050 (preferred): Where app should bind
- Port 5051 (fallback): Where app binds if 5050 is busy (BUG)
- nginx proxies :5050 → :5050 via HTTPS

---

## Next Steps After Fixes

Once both issues are resolved:

1. ✅ Commit deploy.yml fix
2. ✅ Verify hub summary matches on localhost and EC2
3. ✅ Test WA message queue (scheduled sends at 07:30, 12:30, 18:30 SAST)
4. ✅ Mark Phase 4 complete in PHASE_4_HANDOFF.md

---

## Questions for Fidel (Optional)

- Has promo_messages.json ever been modified by a scheduled task or automated process?
- Are there any other data initialization scripts that run on app startup?
- Should the deploy script also update any other files (config, secrets)?

