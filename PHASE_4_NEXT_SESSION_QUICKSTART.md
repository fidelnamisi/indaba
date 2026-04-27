# Phase 4 Next Session — Quick Start (Copy/Paste Ready)

**2 issues to fix. ~30 minutes.**

---

## Issue #1: Messages Queue Discrepancy

**Problem:** EC2 shows 14 queued messages, localhost shows 22. File is correct but app is filtering/modifying it.

**Diagnose (copy/paste):**

```bash
cd ~/Indaba

# Local file check
echo "LOCAL:"
md5 data/promo_messages.json
python3 -c "import json; data=json.load(open('data/promo_messages.json')); print('Queued:', sum(1 for m in data['messages'] if m.get('status')=='queued'))"

# EC2 file check
echo ""
echo "EC2:"
ssh -i ec2-key.pem ubuntu@13.218.60.13 "md5sum /opt/indaba-app/data/promo_messages.json && python3 -c \"import json; data=json.load(open('/opt/indaba-app/data/promo_messages.json')); print('Queued:', sum(1 for m in data['messages'] if m.get('status')=='queued'))\""

# Search for code that modifies the file
echo ""
echo "CODE SEARCH:"
grep -r "promo_messages.json" routes/ utils/ --include="*.py" | grep -E "write|dump|replace|json.dumps"
```

**If files are different:**
Check these files for initialization code that writes to promo_messages.json:
- `utils/migrate.py` (especially `sync_existing_data_to_assets()`)
- `routes/promo_messages.py`
- Check for git hooks: `find .git/hooks -type f` (especially post-merge)

**If files match but API shows different count:**
- The app is filtering messages during initialization
- Check `app.py` line 143: `retry_failed_messages()` 
- Check that function in `utils/migrate.py`
- Look for code that changes message status from 'queued' to something else

**Fix:** Once you find the code, update it to not filter out queued messages, or if it's intentional, update localhost to match EC2 behavior.

---

## Issue #2: Port Race Condition in Deploy

**Problem:** When deploy restarts indaba-app, old process doesn't release port 5050, so new process binds to 5051. Breaks nginx.

**Fix (copy/paste):**

```bash
cd ~/Indaba

# Open the deploy workflow
cat .github/workflows/deploy.yml | head -50

# Find the "Restart Indaba App" section (should have: systemctl restart indaba-app)
# Replace that section with this:

# Edit the file - look for the restart line and replace it
nano .github/workflows/deploy.yml

# In the "Restart Indaba App" step, change:
#   ssh -i ~/ec2-key.pem ubuntu@13.218.60.13 'sudo systemctl restart indaba-app'
# To:
#   ssh -i ~/ec2-key.pem ubuntu@13.218.60.13 '
#     sudo pkill -9 -f "python.*app.py" || true
#     sudo lsof -i :5050 -S -t | xargs -r kill -9 || true
#     sudo lsof -i :5051 -S -t | xargs -r kill -9 || true
#     sleep 2
#     sudo systemctl restart indaba-app
#   '

# Commit and push
git add .github/workflows/deploy.yml
git commit -m "Harden deploy: kill old processes before restart (Phase 4)"
git push origin main
```

---

## Validation

**After both fixes, run this:**

```bash
cd ~/Indaba

echo "=== FINAL VALIDATION ==="
echo ""
echo "LOCALHOST:"
curl -s http://localhost:5050/api/hub/summary | python3 -c "import json, sys; d=json.load(sys.stdin); print('Messages queued:', d['promote']['messages_queued']); print('Pipeline:', d['pipeline'])"

echo ""
echo "EC2:"
curl -s https://indaba.realmsandroads.com/api/hub/summary | python3 -c "import json, sys; d=json.load(sys.stdin); print('Messages queued:', d['promote']['messages_queued']); print('Pipeline:', d['pipeline'])"

echo ""
echo "✅ Phase 4 COMPLETE if both show: messages_queued=22, pipeline={producing: 62, promoting: 6, publishing: 6}"
```

---

## Reference

**Full Details:** See `PHASE_4_DATA_SYNC_HANDOFF.md`

**Key Files:**
- `.github/workflows/deploy.yml` — deploy script
- `utils/migrate.py` — app initialization logic
- `routes/promo_messages.py` — message handling
- `data/promo_messages.json` — message queue file

**EC2 SSH:** `ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13`
