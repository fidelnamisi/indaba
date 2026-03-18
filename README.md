# Indaba — Morning Briefing System

> *Every morning. Take stock. Decide what matters. Begin.*

---

## First-time setup

**1. Install Flask (once only)**

```bash
pip install flask
```

**2. Launch Indaba**

```bash
cd /path/to/indaba
python launch.py
```

Your browser opens automatically at `http://localhost:5050`.

**That's it.** Your projects are pre-loaded from the spec. Start using it immediately.

---

## Daily use

Double-click `launch.py` or run `python launch.py` from your terminal. The browser opens automatically. Close the terminal window (or press `Ctrl+C`) to shut Indaba down at the end of the day.

---

## Your data

All data lives in the `data/` folder as plain JSON files:

| File | Contents |
|------|----------|
| `data/projects.json` | All projects — phase, next action, deadlines |
| `data/settings.json` | Briefing time, window end, lead measure targets |
| `data/lead_measures.json` | Monthly scoreboard data |
| `data/content_pipeline.json` | Patreon / website chapter tracker |

Back these up to your DEVONthink or wherever. They are human-readable and editable in any text editor.

---

## Mobile access with Tailscale (free, 5 minutes)

Tailscale creates a private network between your devices. Once set up, you can open Indaba on your phone from anywhere — as long as your laptop is running.

**Step 1.** Download Tailscale: https://tailscale.com/download
Install on your Mac and on your phone.

**Step 2.** Create a free account and sign in on both devices.

**Step 3.** Find your laptop's Tailscale IP address:
- Open the Tailscale menu bar icon on your Mac
- Your IP looks like `100.x.x.x`

**Step 4.** On your phone browser, go to:
```
http://100.x.x.x:5050
```

That's it. Same Indaba, same data, accessible from anywhere — coffee shop, waiting room, wherever. No cloud. No sync. One running instance.

---

## Plugins

Plugins live in the `plugins/` folder. Each plugin is a self-contained Python module.

**Currently installed:**
- **SuperProductivity Export** — exports your current next-actions as a SuperProductivity-compatible JSON file. Click the `⬡` button in the top bar → Export.

**Adding a new plugin:**

1. Create a folder: `plugins/your_plugin_name/`
2. Add `__init__.py` that defines a class inheriting from `IndabaPlugin` (see `plugins/base.py`)
3. Set `PLUGIN_CLASS = YourClass` at the bottom of the file
4. Restart Indaba — it appears automatically under `⬡` Plugins

---

## LivingWriter

LivingWriter is the creative development pipeline — a separate Cowork build that manages story projects from raw impulse through six phases to completed first draft.

When you're ready to start it:
1. Open a new Cowork chat
2. Paste in the LivingWriter context document
3. Build it

Indaba will prompt you to start a LivingWriter record whenever you add a Creative Development project.

---

## Version 2 (planned)

- Live CRM read — surface overdue follow-ups from Laravel directly
- DEVONthink integration — surface relevant materials when a funding opportunity is active
- Weekly schedule generator — given a script deadline, back-calculate session plan
- Crux checker — tick off cruxes as honoured after a draft session
- Session timer — visible countdown with gentle end-of-session alert
- Full cloud sync option (for true mobile independence)
