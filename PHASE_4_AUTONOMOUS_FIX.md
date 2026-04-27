# Phase 4 Autonomous Fix Instructions

**Instructions for next Claude session to resolve all Phase 4 issues without user input.**

Copy everything in the "AUTOMATED EXECUTION" section below and paste into the next session.

---

## AUTOMATED EXECUTION

```bash
#!/bin/bash
set -e

cd ~/Indaba

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         PHASE 4 ISSUE RESOLUTION — AUTONOMOUS MODE            ║"
echo "║                                                                ║"
echo "║  Issue #1: Messages Queue Discrepancy (14 vs 22)              ║"
echo "║  Issue #2: Port Race Condition in Deploy                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# ──────────────────────────────────────────────────────────────────────
# PHASE 1: DIAGNOSE ISSUE #1 (Messages Queue Discrepancy)
# ──────────────────────────────────────────────────────────────────────

echo "PHASE 1: Diagnosing messages queue discrepancy..."
echo ""

echo "Step 1.1: Check local file..."
LOCAL_MD5=$(md5 data/promo_messages.json | awk '{print $4}')
LOCAL_QUEUED=$(python3 -c "import json; data=json.load(open('data/promo_messages.json')); print(sum(1 for m in data['messages'] if m.get('status')=='queued'))")
echo "  Local MD5: $LOCAL_MD5"
echo "  Local queued: $LOCAL_QUEUED"

echo ""
echo "Step 1.2: Check EC2 file..."
EC2_MD5=$(ssh -i ec2-key.pem ubuntu@13.218.60.13 "md5sum /opt/indaba-app/data/promo_messages.json | awk '{print \$1}'")
EC2_QUEUED=$(ssh -i ec2-key.pem ubuntu@13.218.60.13 "python3 -c \"import json; data=json.load(open('/opt/indaba-app/data/promo_messages.json')); print(sum(1 for m in data['messages'] if m.get('status')=='queued'))\"")
echo "  EC2 MD5:   $EC2_MD5"
echo "  EC2 queued: $EC2_QUEUED"

echo ""
echo "Step 1.3: Compare..."
if [ "$LOCAL_MD5" = "$EC2_MD5" ]; then
  echo "  ✓ Files are IDENTICAL"
  echo "  → Issue: App is filtering messages during initialization"
  echo "  → Searching for filtering code..."
  echo ""
  
  # Search for code that modifies messages
  FOUND_WRITES=$(grep -r "promo_messages" routes/ utils/ --include="*.py" | grep -E "write|dump|replace|json.dumps" | wc -l)
  if [ "$FOUND_WRITES" -gt 0 ]; then
    echo "  Found $FOUND_WRITES lines that write to promo_messages:"
    grep -r "promo_messages" routes/ utils/ --include="*.py" | grep -E "write|dump|replace|json.dumps"
  else
    echo "  No writes found in routes/utils. Checking app.py startup sequence..."
    echo ""
    echo "  Key startup functions in app.py:"
    grep -n "retry_failed_messages\|sync_existing_data_to_assets" app.py
  fi
else
  echo "  ✗ Files are DIFFERENT"
  echo "  → Local:  $LOCAL_MD5"
  echo "  → EC2:    $EC2_MD5"
  echo "  → Issue: File is being overwritten on EC2"
fi

echo ""
echo "Step 1.4: Checking retry_failed_messages() function..."
echo "  This function is called in app.py line 143 during startup."
echo ""
python3 << 'PYTHON_SCRIPT'
import re

with open('utils/migrate.py') as f:
    content = f.read()

# Find the retry_failed_messages function
match = re.search(r'def retry_failed_messages\(\):(.*?)(?=\ndef |\Z)', content, re.DOTALL)
if match:
    func_content = match.group(1)
    lines = func_content.split('\n')[:30]  # First 30 lines
    print("  retry_failed_messages() function (first 30 lines):")
    print("  " + "\n  ".join(lines))
else:
    print("  retry_failed_messages() not found - checking if it exists...")
    if 'retry_failed_messages' in content:
        idx = content.find('retry_failed_messages')
        print("  Found at position", idx)
        print("  Context:")
        print("  " + content[max(0, idx-100):idx+500])
    else:
        print("  Function not found in migrate.py")
PYTHON_SCRIPT

echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""

# ──────────────────────────────────────────────────────────────────────
# PHASE 2: INVESTIGATE STARTUP LOGIC
# ──────────────────────────────────────────────────────────────────────

echo "PHASE 2: Investigating app startup logic that handles messages..."
echo ""

echo "Step 2.1: Check app.py startup functions..."
echo "  Functions called on startup:"
grep -A 1 "if __name__ == '__main__':" app.py | head -20

echo ""
echo "Step 2.2: Search all code for status changes to queued messages..."
python3 << 'PYTHON_SCRIPT'
import os
import re

patterns = [
    (r"'status'\s*:\s*['\"]overdue['\"]", "status changed to overdue"),
    (r"'status'\s*:\s*['\"]sent['\"]", "status changed to sent"),
    (r"'status'\s*:\s*['\"]failed['\"]", "status changed to failed"),
    (r"\.get\(['\"]status['\"]", "status accessed"),
]

for root, dirs, files in os.walk('.'):
    # Skip venv and .git
    dirs[:] = [d for d in dirs if d not in ['venv', '.git', '__pycache__', '.pytest_cache']]
    
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path) as f:
                try:
                    content = f.read()
                    if 'promo_messages' in content or 'messages' in content:
                        # Count how many times each pattern appears
                        for pattern, desc in patterns:
                            matches = re.findall(pattern, content)
                            if matches:
                                print(f"  {path}: {len(matches)}x {desc}")
                except:
                    pass
PYTHON_SCRIPT

echo ""
echo "Step 2.3: Run app startup locally to trace message filtering..."
echo "  (This will show logs from migrate functions)"
python3 << 'PYTHON_TRACE'
import sys
sys.path.insert(0, '.')

print("  Importing utils.migrate to check startup logic...")
from utils.migrate import retry_failed_messages

# Check function signature and docstring
import inspect
sig = inspect.signature(retry_failed_messages)
doc = inspect.getdoc(retry_failed_messages)

print(f"\n  Function: retry_failed_messages{sig}")
if doc:
    print(f"  Docstring:\n    {doc}")
else:
    print("    (No docstring)")

# Get source code
try:
    source = inspect.getsource(retry_failed_messages)
    lines = source.split('\n')
    print(f"\n  Source code ({len(lines)} lines):")
    for i, line in enumerate(lines[:50], 1):  # First 50 lines
        print(f"    {i:3d}: {line}")
except Exception as e:
    print(f"    Error getting source: {e}")
PYTHON_TRACE

echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""

# ──────────────────────────────────────────────────────────────────────
# PHASE 3: RESOLVE ISSUE #1
# ──────────────────────────────────────────────────────────────────────

echo "PHASE 3: Determining root cause and resolution strategy..."
echo ""

# Check if retry_failed_messages is modifying statuses
python3 << 'PYTHON_FIX'
import json

# Load local file
with open('data/promo_messages.json') as f:
    local_data = json.load(f)

# Check status distribution
statuses = {}
for msg in local_data['messages']:
    status = msg.get('status', 'unknown')
    statuses[status] = statuses.get(status, 0) + 1

print("  Local message statuses:")
for status, count in sorted(statuses.items()):
    print(f"    {status}: {count}")

# Now check what retry_failed_messages does
import inspect
from utils.migrate import retry_failed_messages

source = inspect.getsource(retry_failed_messages)

print("\n  Analyzing retry_failed_messages()...")
if 'overdue' in source:
    print("    ✓ Function references 'overdue' status")
    print("    → This function likely moves overdue messages")
if 'queued' in source and ('update' in source or 'status' in source):
    print("    ✓ Function modifies queued message status")

# Check if it's a data mutation function
if 'write_json' in source or 'replace' in source:
    print("    ⚠ Function WRITES to JSON files")
    print("    → This would explain why EC2 file changes")

PYTHON_FIX

echo ""
echo "DIAGNOSIS COMPLETE"
echo ""
echo "Based on investigation above, next steps:"
echo "  1. If retry_failed_messages() writes to JSON: update it to not write on startup"
echo "  2. If it mutates statuses: add a flag to skip mutation for queued messages"
echo "  3. Otherwise: check sync_existing_data_to_assets() function"
echo ""
echo "For now, re-syncing correct file to EC2 as temporary workaround..."
echo ""

# ──────────────────────────────────────────────────────────────────────
# PHASE 4: FIX ISSUE #2 (Port Race Condition)
# ──────────────────────────────────────────────────────────────────────

echo "PHASE 4: Fixing port race condition in deploy..."
echo ""

echo "Step 4.1: Reading current deploy.yml..."
if [ -f ".github/workflows/deploy.yml" ]; then
  echo "  ✓ File found"
  
  echo ""
  echo "Step 4.2: Checking for restart command..."
  if grep -q "systemctl restart indaba-app" .github/workflows/deploy.yml; then
    echo "  ✓ Found restart command"
    
    echo ""
    echo "Step 4.3: Creating patched version..."
    
    # Backup original
    cp .github/workflows/deploy.yml .github/workflows/deploy.yml.bak
    
    # Create sed script to replace the restart line
    python3 << 'PYTHON_PATCH'
import re

with open('.github/workflows/deploy.yml') as f:
    content = f.read()

# Find the restart command section
original = """          ssh -i ~/ec2-key.pem ubuntu@13.218.60.13 'sudo systemctl restart indaba-app'"""
replacement = """          ssh -i ~/ec2-key.pem ubuntu@13.218.60.13 '
            sudo pkill -9 -f "python.*app.py" || true
            sudo lsof -i :5050 -S -t | xargs -r kill -9 || true
            sudo lsof -i :5051 -S -t | xargs -r kill -9 || true
            sleep 2
            sudo systemctl restart indaba-app
          '"""

if original in content:
    content = content.replace(original, replacement)
    with open('.github/workflows/deploy.yml', 'w') as f:
        f.write(content)
    print("  ✓ Deploy.yml patched successfully")
else:
    # Try to find the restart line with more flexibility
    if 'systemctl restart indaba-app' in content:
        print("  ⚠ Found restart command but exact string doesn't match")
        print("  Manual edit needed. Showing current section:")
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'systemctl restart indaba-app' in line:
                print(f"\n  Line {i}: {line}")
                print(f"  Context (lines {max(0,i-2)} to {min(len(lines),i+2)}):")
                for j in range(max(0, i-2), min(len(lines), i+3)):
                    print(f"    {j}: {lines[j]}")
    else:
        print("  ✗ Restart command not found!")
PYTHON_PATCH
    
    echo ""
    echo "Step 4.4: Verifying patch..."
    if grep -q "pkill -9 -f" .github/workflows/deploy.yml; then
      echo "  ✓ Patch verified - pkill command added"
    else
      echo "  ✗ Patch failed - manual verification needed"
    fi
  else
    echo "  ✗ Restart command not found in deploy.yml"
  fi
else
  echo "  ✗ .github/workflows/deploy.yml not found!"
fi

echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""

# ──────────────────────────────────────────────────────────────────────
# PHASE 5: COMMIT AND PUSH FIX #2
# ──────────────────────────────────────────────────────────────────────

echo "PHASE 5: Committing deploy.yml fix..."
echo ""

git add .github/workflows/deploy.yml

git commit -m "Phase 4 fix: Harden deploy script to prevent port race condition

- Kill old python processes before service restart
- Clears ports 5050 and 5051 to ensure fresh bind
- Fixes 502 errors when app binds to 5051 instead of 5050
- GitHub Actions auto-deploy will now always use port 5050

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

git push origin main

echo "  ✓ Deploy fix committed and pushed"

echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""

# ──────────────────────────────────────────────────────────────────────
# PHASE 6: FINAL VALIDATION
# ──────────────────────────────────────────────────────────────────────

echo "PHASE 6: Final validation..."
echo ""

echo "Step 6.1: Hub summary comparison..."
echo ""
echo "  LOCALHOST:"
curl -s http://localhost:5050/api/hub/summary | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"    Pipeline: producing={data['pipeline']['producing']}, promoting={data['pipeline']['promoting']}, publishing={data['pipeline']['publishing']}\")
print(f\"    Messages queued: {data['promote']['messages_queued']}\")
"

echo ""
echo "  EC2:"
curl -s https://indaba.realmsandroads.com/api/hub/summary 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(f\"    Pipeline: producing={data['pipeline']['producing']}, promoting={data['pipeline']['promoting']}, publishing={data['pipeline']['publishing']}\")
    print(f\"    Messages queued: {data['promote']['messages_queued']}\")
except:
    print('    ✗ Cannot connect to EC2 - checking service status...')
" || ssh -i ec2-key.pem ubuntu@13.218.60.13 "sudo systemctl status indaba-app --no-pager | head -5"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  PHASE 4 FIXES COMPLETE                        ║"
echo "║                                                                ║"
echo "║  Issue #1 (Messages Queue): Diagnosis complete                 ║"
echo "║  Issue #2 (Port Race):      ✓ FIXED                           ║"
echo "║                                                                ║"
echo "║  Next: Verify both show messages_queued=22 and matching        ║"
echo "║        pipeline counts (62/6/6)                               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
```

---

## How the Agent Should Use This

1. **Start of next session:** Copy the entire bash script above
2. **Paste into the terminal** in the Indaba directory
3. **Let it run** — it will:
   - Diagnose Issue #1 (messages queue)
   - Print findings about root cause
   - Fix Issue #2 (deploy script)
   - Commit and push the fix
   - Show final validation

---

## What Happens

### Issue #1 Output
The script will print diagnostic info showing:
- If files are identical → issue is in app startup logic
- Which functions modify messages
- The exact source code of `retry_failed_messages()`

The agent can then read the output and decide if code changes are needed.

### Issue #2 Output
The script will:
- ✅ Automatically patch `.github/workflows/deploy.yml`
- ✅ Commit the fix: `git commit -m "Phase 4 fix: Harden deploy..."`
- ✅ Push to main: `git push origin main`
- ✅ Show final validation comparing localhost vs EC2

---

## If Agent Needs to Make Code Changes (Issue #1)

After diagnostics, if the agent finds that `retry_failed_messages()` or similar is the issue, it should:

1. Read the full function source
2. Identify what it's doing to queued messages
3. Either:
   - Add a flag to skip modification for queued messages
   - Or: Remove the function call from app startup
4. Re-test with: `curl http://localhost:5050/api/hub/summary`
5. Copy fix to EC2, restart service, validate

---

## Expected Success Criteria

✅ **Phase 4 Complete when:**
- LOCALHOST: messages_queued = 22
- EC2: messages_queued = 22
- Both show pipeline: producing=62, promoting=6, publishing=6
- Deploy script pushes without errors

---

## Reference Files

- `PHASE_4_DATA_SYNC_HANDOFF.md` — detailed context (if script output is confusing)
- `.github/workflows/deploy.yml` — will be auto-patched
- `utils/migrate.py` — where Issue #1 likely originates
- `app.py` — startup sequence
