# Phase 4 EC2 Testing — Defect Report

**Date:** 2026-04-27  
**Model:** Haiku  
**Session:** Diagnosis Only (No Fixes)  
**Reference:** localhost:5050 vs https://indaba.realmsandroads.com

---

## Executive Summary

EC2 deployment has a **critical data seeding issue**. During the deploy process, not all necessary data files were copied to `/opt/indaba-app/data/`, and several files that were copied are truncated or corrupted. The Indaba backend is running, but the frontend will experience missing data and degraded functionality in Projects, Earnings, and Lead Measures sections.

---

## Defects by Priority

### P1 — Data Missing / Critical Breakage

#### 1.1 Missing Data Files (13 files)
**Impact:** Projects, Earnings, Lead Measures sections will crash or display empty.

| File | Local Size | EC2 Status | Used By |
|------|-----------|-----------|----------|
| `projects.json` | 14K | ❌ MISSING | Projects dashboard, work tracking |
| `lead_measures.json` | 141B | ❌ MISSING | Dashboard summary, KPI tracking |
| `earnings.json` | 136B | ❌ MISSING | Earnings dashboard |
| `chapters.json` | 18K | ❌ MISSING | Chapter reference data |
| `cowork_alerts.json` | 1.4K | ❌ MISSING | Scheduled job failure alerts (SLA requirement) |
| `daily_log.json` | 1.6K | ❌ MISSING | Daily activity logging |
| `dormant.json` | 2B | ❌ MISSING | Dormant project tracking |
| `entities.json` | 15K | ❌ MISSING | CRM entity definitions |
| `generated_assets.json` | 255K | ❌ MISSING | Cache of AI-generated assets |
| `generated_pipeline_entries.json` | 9.1K | ❌ MISSING | Tracked generated content |
| `inbox.json` | 2B | ❌ MISSING | Inbox tracking |
| `merged_chapters.json` | 1.1M | ❌ MISSING | Merged chapter content (largest file!) |
| `promo_books.json` | 13K | ❌ MISSING | Serialisation book tracking (Love Back chunks) |

**Expected Behavior:** Dashboard loads, all sections functional, data persists.  
**Actual Behavior:** Backend doesn't crash, but sections that read these files will error or show empty results.

---

#### 1.2 Severely Truncated Data Files (5 files)
**Impact:** WA messages not queued, contact/lead sync broken, pipeline incomplete.

| File | Local Size | EC2 Size | Loss | Issue |
|------|-----------|----------|------|-------|
| `promo_messages.json` | 96K | 607B | **99%** | Messages queue is virtually empty. Scheduled sends won't work. |
| `content_pipeline.json` | 678K | 610K | 68K | Chapters are missing or truncated. Hub shows wrong counts. |
| `assets.json` | 523K | 272K | 251K | Generated assets missing. |
| `modules.json` | 91K | 31K | 60K | Module metadata lost. |
| `works.json` | 85K | 27K | 58K | Work definitions incomplete. |

**Expected Behavior:** EC2 has full copy of local data, messages queue works, pipeline matches localhost.  
**Actual Behavior:** Hub summary shows different pipeline counts (64 vs 62 producing, 3 vs 6 promoting, 0 vs 22 messages). Sync is severely out of date.

**Specific Evidence:**
```
Hub Summary Mismatch:
  Local:  62 producing, 6 promoting, 6 publishing, 22 messages queued
  EC2:    64 producing, 3 promoting, 7 publishing, 0 messages queued
```

---

#### 1.3 CRM Data Severely Truncated
**Impact:** Contact and lead import/sync features broken.

| File | Local | EC2 | Loss |
|------|-------|-----|------|
| `crm_contacts.json` | 7.4K | 20B | **>99%** |
| `crm_leads.json` | 29K | 17B | **>99%** |

**Expected Behavior:** CRM data available for sync and merging with promo data.  
**Actual Behavior:** CRM sections will show zero contacts/leads.

---

### P2 — Data Sync Out of Sync

#### 2.1 Messages Queue Not Running / Not Synced
**Location:** `/api/promo/messages` endpoint  
**Impact:** WhatsApp scheduled sends won't execute.

**Expected Behavior:** Messages at `status: "queued"` are sent by scheduled tasks at 07:30, 12:30, 18:30 SAST.  
**Actual Behavior:** Queue is empty (607B file). Even if messages were queued locally, sync script doesn't push `promo_messages.json` to EC2.

**Note:** SLA Section 2.7 requires messaging queue to work. The sync script only pushes 3 files (`promo_leads`, `promo_contacts`, `promo_proverbs`), not `promo_messages`.

---

#### 2.2 No Data Seeding During Deploy
**Impact:** Fresh EC2 deploy always has stale/partial data.

**Root Cause:** The deploy process (GitHub Actions + Amplify) does not seed EC2 data directory with local files. Only the source code is deployed.

**Expected Behavior:** Deploy script copies all necessary data files from local to EC2 or provides instructions for manual seeding.  
**Actual Behavior:** EC2 starts with empty or very old data directory.

---

### P3 — UI/UX Issues

#### 3.1 Projects Tab Will Show Empty (Cosmetic but Breaking)
**Location:** `/projects` page  
**Impact:** Projects section will not load project list.

**Expected Behavior:** Projects list loads from `projects.json`, shows all active/completed projects.  
**Actual Behavior:** File doesn't exist on EC2; endpoint may 404 or return empty array.

---

#### 3.2 Earnings Dashboard Broken
**Location:** `/earnings` page (if implemented)  
**Impact:** Earnings data not accessible.

**Expected Behavior:** Earnings dashboard shows Patreon earnings over time.  
**Actual Behavior:** File doesn't exist; section may 404 or show empty.

---

#### 3.3 Lead Measures Dashboard Missing
**Location:** Dashboard hub / KPI section  
**Impact:** Cannot view lead measures (pitch count, meeting count, follow-ups).

**Expected Behavior:** Hub summary includes lead measures stats.  
**Actual Behavior:** File doesn't exist; hub will either error or omit this section.

---

## Root Cause Analysis

### Deployment Flow Issue
1. **What happened:** EC2 instance was provisioned and Indaba code was deployed via GitHub Actions + Amplify.
2. **What was deployed:** Only the codebase (app.py, routes/, static/, etc.). Data files were not copied.
3. **What should happen:** Either (a) data files should be copied during deploy, or (b) EC2 should have a manual or automated data-sync step after deploy.
4. **Current state:** EC2 has an old/partial snapshot of data, likely from initial setup or an incomplete previous deploy attempt.

### Sync Script Gap
- `./scripts/sync_to_ec2.sh` only syncs 3 files: `promo_leads.json`, `promo_contacts.json`, `promo_proverbs.json`.
- It does NOT sync: `projects.json`, `earnings.json`, `lead_measures.json`, `promo_messages.json`, `content_pipeline.json`, etc.
- This means EC2 will always be out of sync for data that's edited locally.

---

## Testing Summary

### API Tests Performed
- ✅ Hub summary: loads, but with mismatched counts
- ✅ Content pipeline: loads, but truncated
- ✅ Promo contacts: loads, but count matches (both have minimal data)
- ✅ Promo leads: loads, but count matches (both have minimal data)
- ✅ Promo proverbs: loads, but count matches
- ✅ Works: loads, but truncated
- ✅ Promo settings: loads, matches localhost
- ⚠️ Projects: endpoint not tested (no dedicated `/api/projects` endpoint found)
- ⚠️ Lead measures: endpoint not tested (no dedicated endpoint found)
- ⚠️ Earnings: endpoint not tested (no dedicated endpoint found)

### Data File Comparison
- ✅ Checked file sizes locally vs EC2
- ✅ Verified which files are missing
- ✅ Confirmed truncated files
- ✅ Identified 13 completely missing files, 5 truncated files

### Pages Tested
- ✅ `/` (redirect) — works on both
- ✅ `/promoting` (HTML load) — works on both
- ✅ `/publishing` (HTTP 200) — works on both
- ✅ `/works` (redirect) — works on both

---

## Recommendations (Handoff to Sonnet)

### Immediate Fixes (Critical)
1. **Seed EC2 data directory** — copy all 34 essential data files from local to EC2.
2. **Verify file integrity** — after copy, check file sizes match and validate JSON structure.
3. **Restart indaba-app** — trigger a reload to pick up the new data.
4. **Test hub summary** — verify pipeline counts match localhost.

### Medium-term Fixes (Recommended)
1. **Expand sync script** — add all local-authoritative files to `sync_to_ec2.sh`:
   - Add: `projects.json`, `earnings.json`, `lead_measures.json`, `promo_messages.json` (consider EC2 as outbox)
   - Document which files are local-authoritative vs EC2-authoritative
2. **Automate data seeding** — include data copy in deploy process or provide a `./scripts/seed_ec2.sh` script.
3. **Add pre-deploy validation** — check that EC2 has all necessary files before marking deploy as complete.

### Testing (Before Handoff to Sonnet)
- After fixes, re-run this checklist on EC2 vs localhost
- Verify hub summary counts match
- Test WA message queue functionality
- Confirm all dashboard sections load without errors

---

## Files to Fix (Complete List)

**Copy from local to EC2:**
```
projects.json
lead_measures.json
earnings.json
chapters.json
cowork_alerts.json
daily_log.json
dormant.json
entities.json
generated_assets.json
generated_pipeline_entries.json
inbox.json
merged_chapters.json
promo_books.json
```

**Verify/Re-sync (truncated files):**
```
promo_messages.json (critical for WA queue)
content_pipeline.json
assets.json
modules.json
works.json
crm_contacts.json
crm_leads.json
```

---

## Next Steps

1. This defect report identifies **scope of work** for the Sonnet session.
2. Sonnet should focus on **data sync and seeding**, not code fixes.
3. After fixes, re-test using this same checklist.
4. Once EC2 matches localhost, mark Phase 4 complete.
