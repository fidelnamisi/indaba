# Phase 4 — EC2 vs Localhost End-to-End Test Session
**Date written:** 2026-04-27
**Purpose:** Surface all defects, failures and missing data in https://indaba.realmsandroads.com
  compared to the working localhost:5050 reference.

---

## Session Setup

- **Model:** Haiku (cheaper — this is pure testing/comparison work, no coding)
- **Reference:** `localhost:5050` (authoritative, known-good)
- **Target:** `https://indaba.realmsandroads.com` (EC2, needs testing)
- **SSH key:** `~/Indaba/ec2-key.pem`
- **EC2:** `ubuntu@13.218.60.13`

Both URLs must be open in your browser side-by-side during this session.

---

## Your Task

Do a systematic end-to-end comparison of every page and function in Indaba.
For each item: test it on localhost, test it on EC2, record the result.

Produce a **defect list** at the end — each entry with:
- Page / feature
- What works on localhost
- What fails or is wrong on EC2
- Likely cause (missing data, broken route, env var, etc.)

---

## Test Checklist

### Hub / Dashboard
- [ ] Hub summary loads (counts, pipeline stats)
- [ ] All section links navigate correctly

### Pipeline
- [ ] Chapter list loads with correct data
- [ ] Chapter status badges correct
- [ ] Clicking a chapter opens the detail modal with correct data
- [ ] Stage transitions work (e.g. move chapter to next stage)
- [ ] Producing / publishing status toggles work

### People > Contacts
- [ ] Contact list loads (KNOWN BROKEN on EC2 — contacts appear empty)
- [ ] Individual contact detail opens correctly
- [ ] Contact search / filter works

### People > Leads
- [ ] Leads list loads
- [ ] Lead detail opens correctly
- [ ] Lead status updates work

### Promo / WA Channel
- [ ] Proverb library loads
- [ ] Broadcast generation works
- [ ] Broadcast queue / send works
- [ ] Settings (branding, AI provider) load correctly

### Projects
- [ ] Projects list loads
- [ ] Project detail opens
- [ ] Lead measures visible

### Earnings
- [ ] Earnings data loads and displays correctly

### Settings / Config
- [ ] Settings page loads
- [ ] Any save/update actions work

---

## Data to Check on EC2 (via SSH)

Run these to verify data files are present and non-empty:

```bash
ssh -i ~/Indaba/ec2-key.pem ubuntu@13.218.60.13 "
  for f in promo_contacts.json promo_leads.json promo_proverbs.json \
            content_pipeline.json projects.json lead_measures.json earnings.json; do
    echo -n \"\$f: \"
    wc -c /opt/indaba-app/data/\$f 2>/dev/null || echo 'MISSING'
  done
"
```

And compare against local:
```bash
for f in promo_contacts.json promo_leads.json content_pipeline.json projects.json lead_measures.json earnings.json; do
  echo -n "$f: "; wc -c ~/Indaba/data/$f 2>/dev/null || echo 'MISSING'
done
```

---

## API Spot-Checks (run from terminal)

```bash
# Hub summary
curl -s https://indaba.realmsandroads.com/api/hub/summary | python3 -m json.tool | head -30

# Contacts
curl -s https://indaba.realmsandroads.com/api/contacts | python3 -m json.tool | head -20

# Leads
curl -s https://indaba.realmsandroads.com/api/leads | python3 -m json.tool | head -20

# Pipeline
curl -s https://indaba.realmsandroads.com/api/pipeline | python3 -m json.tool | head -30

# Proverbs
curl -s https://indaba.realmsandroads.com/api/proverbs | python3 -m json.tool | head -20
```

---

## At the End of the Session

1. Write a `PHASE_4_DEFECTS.md` listing every defect found
2. Prioritise: P1 (data missing/broken), P2 (UI wrong), P3 (nice-to-fix)
3. Commit the defect list
4. Do NOT attempt fixes in this session — this session is diagnosis only
5. Hand off to a Sonnet session for the fixes
