# Indaba — Claude SLA
### Living Service Level Agreement between Fidel Namisi and Claude
**Created:** 2026-03-20 | **Last updated:** 2026-03-20

This document is a living agreement. Claude reads it at the start of every Indaba-related session and updates it as tasks are completed, new commitments are made, or priorities shift. Fidel can edit it directly at any time.

---

## Part 1 — Accountability Commitments (Claude surfaces, Fidel executes)

These are tasks only Fidel can authorise or send, but where Claude's job is to make sure they never stay invisible.

### 1.1 Website Chapter Publishing
- **Status:** ✅ INFRASTRUCTURE LIVE — Website publishing feature built (2026-03-28). Prose/author note/header image fields added to pipeline. Publish to Website button in Publishing tab. Bulk publish. Deploy trigger.
- **Scope:** 53 chapters across OAO (9), ROTRQ (8+4), MOSAS (36) — all `website_status: not_started`. Ready to publish once prose is added.
- **Remaining:** Feature 2 (Audio publishing) deferred to next session — see HANDOFF.md.
- **Claude's commitment:** Surface unpublished chapter count at the start of every session until all are live.
- **Next action:** Fidel adds prose to chapters → press "Publish to Website" per chapter, or bulk-select and publish all → deploy

### 1.2 WhatsApp Channel Posting ("Wisdom and Love Stories")
- **Status:** ⚠️ STALLED — posting_log shows last post on 2026-03-16 (Patreon only). WA channel = 0 posts.
- **Claude's commitment:** At the start of every session, report days since last WA post and surface today's suggested content (next unused proverb or next chapter teaser). Make it trivially easy to send.
- **Next action:** Populate proverb library (Claude can do this now) → generate proverb images → establish a posting rhythm

### 1.3 Patreon Serialised Fiction — Stuck Chapter
- **Status:** ⚠️ STALLED — ROTRQ Chapter 1 has been `patreon_status: in_progress` since at least 2026-03-16 with no resolution
- **Claude's commitment:** Flag any chapter stuck at `in_progress` on any platform for more than 7 days. Ask Fidel directly: was it sent and needs marking live, or is there a real block?
- **Next action:** Fidel confirms ROTRQ ch1 Patreon status → update pipeline → move to ch2

### 1.4 VIP Group Posting
- **Status:** ⚠️ STALLED — ROTRQ Chapter 1 also stuck at `vip_group_status: in_progress`
- **Claude's commitment:** Same as 1.3 — flag stale `in_progress` entries and prompt resolution
- **Next action:** Resolve alongside 1.3

### 1.5 Patreon Upgrades Campaign
- **Status:** ⚠️ NO ACTIVITY — project exists, phase "New", no logged actions
- **Claude's commitment:** Remind Fidel weekly until at least one action is logged against this project
- **Next action:** Fidel defines the first concrete action → Claude drafts any supporting copy

### 1.6 Lead Measures Logging
- **Status:** ⚠️ UNDERFED — only March 2026 data, minimal entries (1 pitch, 0 meetings, 0 follow-ups)
- **Claude's commitment:** At the start of any session touching Indaba, ask if lead measures have been updated for the current week
- **Next action:** Fidel logs current week's numbers

### 1.7 Retreat / Recollection Invites
- **Status:** ⚠️ NO MODULE YET — lives in Fidel's head, not in Indaba
- **Claude's commitment:** Remind Fidel to provide the next event date so it can be tracked. Once a date is given, surface it at every session until invites are confirmed sent.
- **Next action:** Fidel provides next event details → Claude writes invite copy and logs the event

---

## Part 2 — Automation Commitments (Claude executes independently)

These are tasks Claude can handle without Fidel's involvement, or with minimal input.

### 2.1 Proverb Library Population
- **Status:** 🔴 PENDING — only 1 proverb in system ("Spare the rod, spoil the child" — not even African)
- **Ready:** YES — Claude can generate and add 50–100 African proverbs to `promo_proverbs.json` immediately
- **Trigger:** Fidel says "populate the proverbs" → Claude executes in-session
- **Last done:** Never

### 2.2 WhatsApp Post Copy (Chapter Promos)
- **Status:** 🔴 PENDING — 53 chapters have taglines and blurbs, zero WA posts drafted
- **Ready:** YES — Claude generates all 53 posts, formatted for "Wisdom and Love Stories," with CTA
- **Trigger:** Fidel says "write the WA posts" → Claude executes in-session, saves to a file
- **Last done:** Never

### 2.3 Proverb Image Generation
- **Status:** 🔴 PENDING — depends on 2.1 (proverb library) and agreed visual style
- **Ready:** YES once visual style is confirmed (Imagen 3, 16:9, same pipeline as chapter banners)
- **Trigger:** Fidel confirms visual style → Claude runs batch generation
- **Last done:** Never

### 2.4 Chapter HTML Pages — All 53 Remaining
- **Status:** ✅ INFRASTRUCTURE BUILT (2026-03-28) — Indaba now generates and writes HTML files directly to the website directory via the Publish to Website button. No manual page building needed.
- **Ready:** YES — Fidel adds prose per chapter → presses Publish → HTML is written automatically
- **Last done:** Infrastructure built 2026-03-28

### 2.5 Pipeline Status Update After Deploy
- **Status:** ✅ AUTOMATED — pipeline entry `website_status` is now set to `live` automatically by the publish route. No manual update needed.
- **Last done:** Infrastructure built 2026-03-28

### 2.6 Patreon Post Drafts
- **Status:** 🔴 PENDING — all chapters have assets, none have Patreon drafts
- **Ready:** YES — Claude drafts formatted Patreon posts (title, teaser, blurb, CTA) for any or all chapters
- **Trigger:** Fidel says "draft Patreon posts" → Claude produces a batch file
- **Last done:** Never

### 2.7 Automated WA Queue Sending (Scheduled)
- **Status:** ✅ LIVE — three daily sends scheduled (07:30, 12:30, 18:30 SAST, every day)
- **How it works:** Scheduled tasks call `POST http://localhost:5050/api/promo/sender/pop_next`. Only messages with `status: "queued"` are sent. Indaba handles GOWA delivery internally.
- **Failure reporting:** If Indaba or GOWA is not running at send time, a failure alert is written to `./data/cowork_alerts.json` and surfaced at the next session start.
- **Requirement:** Indaba (port 5050) and GOWA (port 3001) must be running on your Mac for sends to succeed.
- **Task IDs:** `indaba-morning-send`, `indaba-midday-send`, `indaba-evening-send` (manageable from Cowork sidebar → Scheduled)
- **Last done:** 2026-03-24

### 2.8 "Love Back" Serialisation Chunks
- **Status:** 🔴 PENDING — `promo_books.json` has the book registered but 0 chunks
- **Ready:** NEEDS DOCX — if manuscript is accessible, Claude splits it into ~300-word chunks and writes to JSON
- **Trigger:** Fidel provides file path or uploads the manuscript
- **Last done:** Never

### 2.9 Retreat Invite Copy
- **Status:** 🔴 PENDING — needs event data
- **Ready:** YES once event details are provided (date, location, audience, CTA)
- **Trigger:** Fidel provides event details → Claude writes copy
- **Last done:** Never

---

## Part 3 — Session Start Protocol

At the start of any Cowork session where Indaba is in scope, Claude should:

1. Read this file
2. **Check for send failures:** Read `./data/cowork_alerts.json`. If it exists and contains any alerts with `"resolved": false`, surface them immediately at the top of the session report — before anything else. Format: "⚠️ SEND FAILURES: [slot] at [timestamp] — [error]". These mean a scheduled send was attempted while Indaba or GOWA was not running.
3. Report the following (briefly, not as a wall of text):
   - Days since last WA channel post
   - Any chapters stuck at `in_progress` for 7+ days on any platform
   - Count of unpublished chapters (until all are live)
   - Any SLA items marked OVERDUE below
4. Ask: *"Which of these do you want to act on today?"*

---

## Part 4 — Completed Items

*(Move items here from Parts 1 and 2 when done, with date.)*

| Item | Completed | Notes |
|------|-----------|-------|
| Chapter assets (blurb/tagline/prompt) for all 58 chapters | 2026-03-19 | All 53 pipeline + 5 generated entries complete |
| Chapter 1 HTML pages for OAO, ROTRQ, MOSAS | 2026-03-19 | Deployed with correct titles, taglines, blurbs, banner images |
| Series page cover images (ROTRQ, MOSAS) | 2026-03-19 | Replaced placeholder divs with actual cover art |
| Homepage logo circle | 2026-03-19 | Replaced CSS placeholder with Logo25.jpeg |
| Amplify deploy skill | 2026-03-19 | Created dedicated skill, fixed zip-from-inside-public/ |

---

## Change Log

| Date | Change | By |
|------|---------|----|
| 2026-03-20 | Document created | Claude |
| 2026-03-24 | Added automated send schedule (2.7), failure alert protocol, session start check for cowork_alerts.json | Claude |
