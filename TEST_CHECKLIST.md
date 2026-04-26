# Indaba — Test Checklist (Revised)
**After: Issues 1–10 fixes | Date: 2026-03-27**

> Before testing anything, **restart Flask** (stop the server, run `python3 app.py` again).

---

## EXECUTE Mode

**Test 1 — Auto-loads on page start**
Open the app fresh (or hard-refresh with Cmd+Shift+R).
- The Operational Brain dashboard should appear **immediately** without needing to click EXECUTE first
- NEXT ACTIONS, BLOCKERS, PIPELINE HEALTH, SALES PIPELINE panels should all be visible

**Test 2 — Work titles in NEXT ACTIONS and BLOCKERS**
Look at the Next Actions list and the BLOCKERS panel on the right.
- Work titles should read **"Rise of the Rain Queen"**, **"Outlaws and Outcasts"**, **"Man of Stone and Shadow"**
- *(Your screenshots already showed this working — ✅)*

**Test 3 — BLOCKERS show readable messages**
Look at the BLOCKERS panel.
- Entries should say **"Missing audio"** (already showing) or
- If any say anything about modules, they should say **"Module still in draft — assets locked until status is review or final"**
- Nothing should say "Missing module is_draft"

---

## MANAGE Mode — Inventory

Go to MANAGE → Inventory tab.

**Test 4 — Work cards have correct styling**
Expand a Work.
- Module rows should have proper styling (background, border)
- The status badge (draft/review/final) should be styled, not plain text

**Test 5 — Add Work from Inventory**
Click the **"+ Add Work"** button in the top-right header.
- Modal should appear with Title, Author, Patreon URL, Website URL fields
- Enter a title, click **Save Work**
- Inventory should reload and show the new Work
- *(Then delete it to keep things clean — trash icon should work)*

**Test 6 — Trash icon deletes a Work**
On any Work card in Inventory, click the **🗑️** trash icon.
- A confirmation dialog should appear
- Click OK — the Work should disappear and the list should reload
- *(Test on a throwaway work, not your real ones)*

**Test 7 — Add Module from Inventory**
Expand a Work in Inventory. Click the **"+ Add Module"** button on that Work's header.
- Modal should appear with Title, Status, Prose fields
- Enter a title, click **Add Module**
- The Work should reload showing the new module underneath it

**Test 8 — Edit Module loads prose**
Expand a Work, expand a Module, click **"Edit Module"**.
- Modal should open with Title, Status, and a **Prose textarea**
- If the module has prose, it should be visible in the textarea
- Edit the title, click **Save Changes** — should save and reload

**Test 9 — Missing asset pill opens create modal**
Expand a Work, expand a Module, expand its assets. Find a **❌ missing** asset pill and click it.
- A modal should open saying "Add Manual Asset" with a type dropdown pre-selected
- The subtitle should show the correct Module ID
- Fill in content, click **Create Asset** — the pill should turn ✅ on reload

---

## MANAGE Mode — Serializer

**Test 10 — Serializer has distinction label**
Go to MANAGE → Serializer. When no work is selected, the right panel should say:
> "Select a work to manage its WA serialization. *This is separate from the Inventory module registry.*"

**Test 11 — Batch Queue (if you have pending chunks)**
In the Serializer, select a Work that has pending chunks. If the **"Queue All Pending..."** button appears, click it, set a start date and interval, click **Queue All**.
- It should queue the chunks and show a success toast
- *(Previously this silently failed due to a stale API endpoint)*

---

## MANAGE Mode — Messages

**Test 12 — Message Maker generates without crashing**
Go to MANAGE → Messages. Fill in the **Purpose** field, optionally fill Audience and Tone, click **Generate Message**.
- It should either generate a message or show an AI error toast — it should **not** silently do nothing or throw a JS error in the console
- *(Previously it crashed because it tried to read `mm-event-name` and `mm-event-date` fields that didn't exist in the HTML)*

---

## Reporting failures
If any test fails, note the **test number** and **what you saw** — that's enough to go straight to the fix.
