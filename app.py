"""
Indaba — Morning Briefing System
Flask backend with JSON file storage and plugin architecture.
"""

import json
import os
import uuid
import glob
import importlib
import pkgutil
import re
import csv
import io
import time
from datetime import datetime, date, timedelta
from flask import Flask, jsonify, request, render_template, send_from_directory
from openai import OpenAI

app = Flask(__name__)

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, 'data')
NOTES_DIR  = os.path.join(BASE_DIR, 'notes')
PLUGIN_DIR = os.path.join(BASE_DIR, 'plugins')

# ── Inbox / Dormant constants (defaults — overridable via settings.json) ──────
INBOX_FILE        = 'inbox.json'
DORMANT_FILE      = 'dormant.json'
POSTING_LOG_FILE  = 'posting_log.json'

PROMO_CONTACTS_FILE = 'promo_contacts.json'
PROMO_LEADS_FILE = 'promo_leads.json'
PROMO_MESSAGES_FILE = 'promo_messages.json'
PROMO_PROVERBS_FILE = 'promo_proverbs.json'
PROMO_BOOKS_FILE = 'promo_books.json'
PROMO_SETTINGS_FILE = 'promo_settings.json'
LIVING_WRITER_FILE = 'living_writer.json'

DEFAULT_PROMO_SETTINGS = {
    "ai_providers": {
        "message_maker": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY"
        },
        "book_serializer": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY"
        },
        "wa_post_maker": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY"
        },
        "crm_assist": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY"
        },
        "image_gen": {
            "provider": "",
            "model": "",
            "api_key_env": "",
            "endpoint": ""
        }
    },
    "cta_links": {
        "patreon_url": "",
        "website_url": ""
    },
    "serializer_defaults": {
        "target_chunk_word_count": 300,
        "max_chunk_word_count": 400
    },
    "wa_channel_branding": {
        "channel_name": "",
        "channel_description": "",
        "cta_emoji": "👇",
        "cta_text": "React with an emoji if this resonated with you."
    },
    "max_leads_per_contact": 10
}

MESSAGE_MAKER_SYSTEM_PROMPT = """You are a WhatsApp message writer for a \
South African author and content creator.
Write a single WhatsApp message that achieves the following purpose: \
{purpose}.
Tone: warm, direct, personal. Never corporate. Never salesy.
Length: 50-120 words maximum.
Structure: 1 opening hook sentence. 1-2 sentences of context. \
1 clear call to action.
No emojis unless specified. No bullet points. Plain conversational prose.
End with a single specific action the recipient should take.
Return only the message text. No preamble. No explanation."""

BOOK_SERIALIZER_SYSTEM_PROMPT = """You are serializing a novel chapter into \
WhatsApp-ready segments for a South African author's WhatsApp channel.

Rules:
- Target length per segment: {target_words} words. \
Hard maximum: {max_words} words.
- Cut each segment at the most emotionally charged moment: a cliffhanger, \
unanswered question, or moment of peak suspense. Never cut mid-sentence.
- Each segment must end with this call to action \
(append exactly as written): {cta}
- Do not add chapter headings, segment numbers, or any metadata.
- Return a JSON array. Each element: {{"content": "segment text including \
CTA", "cliffhanger_note": "one sentence explaining why this is the break \
point"}}
- Return only the JSON array. No preamble. No explanation."""

LEVIATHAN_QUESTIONS = [
  {"id":"q1","part":1,"part_label":"The Physical World",
   "question":"What does this world look like from a train window or its equivalent?",
   "genome_refs":["terrain","world_rules"]},
  {"id":"q2","part":1,"part_label":"The Physical World",
   "question":"What is the dominant material of construction and what does that say about the people who built it?",
   "genome_refs":["terrain","historical_catastrophe"]},
  {"id":"q3","part":1,"part_label":"The Physical World",
   "question":"What does the sky look like and what relationship do people have with it?",
   "genome_refs":["terrain","fragments"]},
  {"id":"q4","part":1,"part_label":"The Physical World",
   "question":"What grows here and what has been cleared paved or poisoned?",
   "genome_refs":["terrain","world_rules"]},
  {"id":"q5","part":1,"part_label":"The Physical World",
   "question":"What is the most dangerous place in this world and who lives there?",
   "genome_refs":["terrain","historical_catastrophe"]},
  {"id":"q6","part":2,"part_label":"Time and History",
   "question":"How long ago was the last catastrophe and does anyone alive remember it?",
   "genome_refs":["historical_catastrophe","thematic_values"]},
  {"id":"q7","part":2,"part_label":"Time and History",
   "question":"What is the official version of history and who benefits from it?",
   "genome_refs":["historical_catastrophe","world_rules"]},
  {"id":"q8","part":2,"part_label":"Time and History",
   "question":"What do children learn about the past and what are they not told?",
   "genome_refs":["historical_catastrophe","fragments"]},
  {"id":"q9","part":2,"part_label":"Time and History",
   "question":"What physical evidence of the past has survived and what has been destroyed?",
   "genome_refs":["historical_catastrophe","terrain"]},
  {"id":"q10","part":2,"part_label":"Time and History",
   "question":"Is the world getting better or worse and who decides?",
   "genome_refs":["thematic_values","world_rules"]},
  {"id":"q11","part":3,"part_label":"Power and Order",
   "question":"Who has the power to make others disappear and how do they justify it?",
   "genome_refs":["world_rules","thematic_values"]},
  {"id":"q12","part":3,"part_label":"Power and Order",
   "question":"What holds this world together and what would cause it to collapse?",
   "genome_refs":["world_rules","historical_catastrophe"]},
  {"id":"q13","part":3,"part_label":"Power and Order",
   "question":"Who enforces the rules and what happens to them if they refuse?",
   "genome_refs":["world_rules","terrain"]},
  {"id":"q14","part":3,"part_label":"Power and Order",
   "question":"What is the most dangerous thing a person can do socially in this world?",
   "genome_refs":["world_rules","thematic_values"]},
  {"id":"q15","part":3,"part_label":"Power and Order",
   "question":"Where does legitimate authority come from in this world?",
   "genome_refs":["world_rules","historical_catastrophe"]},
  {"id":"q16","part":4,"part_label":"Economy and Scarcity",
   "question":"What does everyone want and almost nobody can have?",
   "genome_refs":["world_rules","terrain"]},
  {"id":"q17","part":4,"part_label":"Economy and Scarcity",
   "question":"How do people get what they need and what do they have to give up for it?",
   "genome_refs":["terrain","thematic_values"]},
  {"id":"q18","part":4,"part_label":"Economy and Scarcity",
   "question":"What is considered wealth here and how is it displayed or concealed?",
   "genome_refs":["terrain","fragments"]},
  {"id":"q19","part":4,"part_label":"Economy and Scarcity",
   "question":"Who does the work nobody wants to do and what do they get for it?",
   "genome_refs":["terrain","world_rules"]},
  {"id":"q20","part":4,"part_label":"Economy and Scarcity",
   "question":"What can money not buy in this world?",
   "genome_refs":["world_rules","thematic_values"]},
  {"id":"q21","part":5,"part_label":"Society and Belonging",
   "question":"How do people signal which group they belong to?",
   "genome_refs":["terrain","fragments"]},
  {"id":"q22","part":5,"part_label":"Society and Belonging",
   "question":"What is the worst thing you can call someone here and why?",
   "genome_refs":["world_rules","thematic_values"]},
  {"id":"q23","part":5,"part_label":"Society and Belonging",
   "question":"How are outsiders treated and what must they do to be accepted?",
   "genome_refs":["terrain","world_rules"]},
  {"id":"q24","part":5,"part_label":"Society and Belonging",
   "question":"What do people celebrate together and what does that reveal about their values?",
   "genome_refs":["fragments","thematic_values"]},
  {"id":"q25","part":5,"part_label":"Society and Belonging",
   "question":"Who is invisible in this world and who made them that way?",
   "genome_refs":["world_rules","historical_catastrophe"]},
  {"id":"q26","part":6,"part_label":"Intimacy and Family",
   "question":"How do people form lasting bonds here and what threatens them?",
   "genome_refs":["thematic_values","fragments"]},
  {"id":"q27","part":6,"part_label":"Intimacy and Family",
   "question":"What do parents most fear for their children?",
   "genome_refs":["world_rules","thematic_values"]},
  {"id":"q28","part":6,"part_label":"Intimacy and Family",
   "question":"How is romantic love regarded — as necessity luxury or danger?",
   "genome_refs":["thematic_values","world_rules"]},
  {"id":"q29","part":6,"part_label":"Intimacy and Family",
   "question":"What obligations does a person have to their family and what happens if they refuse?",
   "genome_refs":["world_rules","thematic_values"]},
  {"id":"q30","part":6,"part_label":"Intimacy and Family",
   "question":"How do people grieve here and who is allowed to?",
   "genome_refs":["fragments","thematic_values"]},
  {"id":"q31","part":7,"part_label":"Body and Spirit",
   "question":"What do people believe happens after death and how does that shape how they live?",
   "genome_refs":["world_rules","thematic_values"]},
  {"id":"q32","part":7,"part_label":"Body and Spirit",
   "question":"What counts as sacred here and who controls access to it?",
   "genome_refs":["world_rules","historical_catastrophe"]},
  {"id":"q33","part":7,"part_label":"Body and Spirit",
   "question":"How do people mark the transition from child to adult?",
   "genome_refs":["fragments","world_rules"]},
  {"id":"q34","part":7,"part_label":"Body and Spirit",
   "question":"What do people do with their bodies to signal devotion rebellion or status?",
   "genome_refs":["terrain","fragments"]},
  {"id":"q35","part":7,"part_label":"Body and Spirit",
   "question":"What is considered beautiful here and who decides?",
   "genome_refs":["terrain","thematic_values"]},
  {"id":"q36","part":8,"part_label":"Language and Knowledge",
   "question":"What words does this world have that ours does not?",
   "genome_refs":["fragments","world_rules"]},
  {"id":"q37","part":8,"part_label":"Language and Knowledge",
   "question":"What can people not say out loud and how do they say it anyway?",
   "genome_refs":["world_rules","thematic_values"]},
  {"id":"q38","part":8,"part_label":"Language and Knowledge",
   "question":"Who controls what is written down and what happens to forbidden texts?",
   "genome_refs":["world_rules","historical_catastrophe"]},
  {"id":"q39","part":8,"part_label":"Language and Knowledge",
   "question":"What stories do people tell their children to explain why the world is the way it is?",
   "genome_refs":["historical_catastrophe","fragments"]},
  {"id":"q40","part":8,"part_label":"Language and Knowledge",
   "question":"What counts as proof here and who decides what is true?",
   "genome_refs":["world_rules","thematic_values"]},
  {"id":"q41","part":9,"part_label":"Your Characters in This World",
   "question":"What does your protagonist want that this world makes nearly impossible to have?",
   "genome_refs":["characters","world_rules"]},
  {"id":"q42","part":9,"part_label":"Your Characters in This World",
   "question":"Which of this world's rules does your protagonist believe in most deeply?",
   "genome_refs":["characters","world_rules"]},
  {"id":"q43","part":9,"part_label":"Your Characters in This World",
   "question":"Which of this world's rules is your protagonist unknowingly breaking?",
   "genome_refs":["characters","thematic_values"]},
  {"id":"q44","part":9,"part_label":"Your Characters in This World",
   "question":"What part of this world has your protagonist never seen and why?",
   "genome_refs":["characters","terrain"]},
  {"id":"q45","part":9,"part_label":"Your Characters in This World",
   "question":"How has this world wounded your protagonist before the story begins?",
   "genome_refs":["characters","historical_catastrophe"]},
  {"id":"q46","part":9,"part_label":"Your Characters in This World",
   "question":"What does your protagonist believe about this world that is wrong?",
   "genome_refs":["characters","thematic_values"]},
  {"id":"q47","part":9,"part_label":"Your Characters in This World",
   "question":"Which character is most at home in this world and which is most at odds with it?",
   "genome_refs":["characters","world_rules"]},
  {"id":"q48","part":10,"part_label":"The Story Genome Check",
   "question":"Read your Story Genome. What question does it raise that it does not answer?",
   "genome_refs":["characters","thematic_values","world_rules"]},
  {"id":"q49","part":10,"part_label":"The Story Genome Check",
   "question":"Which character's terrain feels thinnest and needs more specificity?",
   "genome_refs":["characters","terrain"]},
  {"id":"q50","part":10,"part_label":"The Story Genome Check",
   "question":"Where does your world feel arbitrary rather than inevitable?",
   "genome_refs":["world_rules","historical_catastrophe"]},
  {"id":"q51","part":10,"part_label":"The Story Genome Check",
   "question":"What is the single most important thing a reader must understand about this world before the story makes sense?",
   "genome_refs":["world_rules","thematic_values","terrain"]},
  {"id":"q52","part":10,"part_label":"The Story Genome Check",
   "question":"If you removed all the plot from this world what would still be in conflict?",
   "genome_refs":["thematic_values","characters","world_rules"]}
]

_DEFAULTS = {
    'inbox_max':         15,
    'dormant_max':       25,
    'inbox_expiry_days': 7,
    'total_project_cap': 8,
    'zone_cap_morning':  3,
    'zone_cap_paid_work': 3,
    'zone_cap_evening':  2,
}

# Keep module-level aliases for brevity (dynamic reads use get_constants())
INBOX_MAX         = _DEFAULTS['inbox_max']
DORMANT_MAX       = _DEFAULTS['dormant_max']
INBOX_EXPIRY_DAYS = _DEFAULTS['inbox_expiry_days']
TOTAL_PROJECT_CAP = _DEFAULTS['total_project_cap']
ZONE_CAPS         = {'morning': _DEFAULTS['zone_cap_morning'],
                     'paid_work': _DEFAULTS['zone_cap_paid_work'],
                     'evening': _DEFAULTS['zone_cap_evening']}

def get_constants():
    """Return editable constants, merging settings.json overrides with defaults."""
    s = read_json('settings.json') or {}
    c = dict(_DEFAULTS)
    for k in _DEFAULTS:
        if k in s:
            try:
                c[k] = int(s[k])
            except (ValueError, TypeError):
                pass
    c['zone_caps'] = {
        'morning':  c['zone_cap_morning'],
        'paid_work': c['zone_cap_paid_work'],
        'evening':  c['zone_cap_evening'],
    }
    return c

# ── File helpers ─────────────────────────────────────────────────────────────

def read_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(filename, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    tmp  = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, path)

def call_ai(provider_key, messages, max_tokens=1000):
    """Generic AI caller using OpenAI-compatible client."""
    settings = read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS
    config = settings.get("ai_providers", {}).get(provider_key)
    if not config:
        raise ValueError(f"AI provider config for '{provider_key}' not found.")
    
    api_key_env = config.get("api_key_env", "")
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise ValueError(f"API key not configured for provider: {provider_key}. "
                         f"Set the {api_key_env} environment variable.")

    # Implementation brief mentions DeepSeek as primary.
    # Defaulting to DeepSeek base URL if provider is deepseek.
    base_url = "https://api.deepseek.com" if config.get("provider") == "deepseek" else None
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=config.get("model", "deepseek-chat"),
        messages=messages,
        max_tokens=max_tokens
    )
    return resp.choices[0].message.content

def process_overdue_queue():
    """Identify and flag queued messages that missed their scheduled time."""
    data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    messages = data.get("messages", [])
    now_str = datetime.utcnow().isoformat() + "Z"
    changed_count = 0
    for m in messages:
        if m.get("status") == "queued" and m.get("scheduled_at"):
            try:
                # Prompt asks to use datetime.fromisoformat for comparison
                sched = datetime.fromisoformat(m["scheduled_at"].replace("Z", "+00:00"))
                now = datetime.fromisoformat(now_str.replace("Z", "+00:00"))
                if sched <= now:
                    m["status"] = "overdue"
                    changed_count += 1
            except (ValueError, TypeError):
                pass
    if changed_count > 0:
        write_json(PROMO_MESSAGES_FILE, data)
    return changed_count

# ── Migrations ────────────────────────────────────────────────────────────────

def migrate():
    """Apply data model migrations on startup."""
    # 1. Projects: add completed fields
    projects = read_json('projects.json') or []
    changed = False
    for p in projects:
        if 'completed' not in p:
            p['completed'] = False
            changed = True
        if 'completed_at' not in p:
            p['completed_at'] = None
            changed = True
    if changed:
        write_json('projects.json', projects)
        print('[Migrate] Added completed fields to projects')

    # 2. Projects: add phases field
    projects = read_json('projects.json') or []
    changed = False
    for p in projects:
        if 'phases' not in p:
            p['phases'] = []
            changed = True
    if changed:
        write_json('projects.json', projects)
        print('[Migrate] Added phases field to projects')

    # 3. Settings: convert phase_templates strings to arrays
    settings = read_json('settings.json') or {}
    pt = settings.get('phase_templates', {})
    changed = False
    for k, v in pt.items():
        if isinstance(v, str):
            pt[k] = [v]
            changed = True
    if changed:
        settings['phase_templates'] = pt
        write_json('settings.json', settings)
        print('[Migrate] Converted phase_templates strings to arrays')

    # 4. Projects: add mission_critical and energy_zone fields
    projects = read_json('projects.json') or []
    changed = False
    for p in projects:
        if 'mission_critical' not in p:
            p['mission_critical'] = False
            changed = True
        if 'energy_zone' not in p:
            p['energy_zone'] = 'flexible'
            changed = True
    if changed:
        write_json('projects.json', projects)
        print('[Migrate] Added mission_critical and energy_zone fields to projects')

    # 5. Projects: rename energy_zone 'flexible' → 'paid_work'
    projects = read_json('projects.json') or []
    changed = False
    for p in projects:
        if p.get('energy_zone') == 'flexible':
            p['energy_zone'] = 'paid_work'
            changed = True
    if changed:
        write_json('projects.json', projects)
        print('[Migrate] Renamed energy_zone flexible → paid_work')

    # 6. Purge expired inbox items (permanent — no recovery)
    inbox = read_json(INBOX_FILE) or []
    now_iso = datetime.now().isoformat()
    original_count = len(inbox)
    inbox = [item for item in inbox if item.get('expires_at', '9999') > now_iso]
    if len(inbox) < original_count:
        write_json(INBOX_FILE, inbox)
        print(f'[Migrate] Purged {original_count - len(inbox)} expired inbox item(s) — permanently deleted')

    # 7b. Projects: add zone_priority field (False for all existing)
    projects = read_json('projects.json') or []
    changed = False
    for p in projects:
        if 'zone_priority' not in p:
            p['zone_priority'] = False
            changed = True
    if changed:
        write_json('projects.json', projects)
        print('[Migrate] Added zone_priority field to projects')

    # 7. Content pipeline: add revision fields
    pipeline = read_json('content_pipeline.json') or []
    changed = False
    for e in pipeline:
        if 'revision' not in e:
            e['revision'] = 1
            changed = True
        for platform in ('vip_group', 'patreon', 'website', 'wa_channel'):
            key = f'{platform}_revision'
            if key not in e:
                e[key] = 0
                changed = True
    if changed:
        write_json('content_pipeline.json', pipeline)
        print('[Migrate] Added revision fields to pipeline entries')

    # 8. Promotion Machine: Initialize directories and storage
    os.makedirs(os.path.join(DATA_DIR, 'cowork_jobs'), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'cowork_results'), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'exports'), exist_ok=True)

    from copy import deepcopy
    promo_init = [
        (PROMO_CONTACTS_FILE, {"contacts": []}),
        (PROMO_LEADS_FILE,    {"leads": []}),
        (PROMO_MESSAGES_FILE, {"messages": []}),
        (PROMO_PROVERBS_FILE, {"proverbs": []}),
        (PROMO_BOOKS_FILE,    {"books": []}),
        (PROMO_SETTINGS_FILE, deepcopy(DEFAULT_PROMO_SETTINGS)),
        (LIVING_WRITER_FILE,  {"stories": []}),
    ]
    for filename, default_data in promo_init:
        if not os.path.exists(os.path.join(DATA_DIR, filename)):
            write_json(filename, default_data)
            print(f'[Migrate] Initialised {filename}')

    # 9. Promotion Machine: Ensure status field and check overdue
    msg_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msg_changed = False
    for m in msg_data.get("messages", []):
        if "status" not in m:
            m["status"] = "queued"
            msg_changed = True
    if msg_changed:
        write_json(PROMO_MESSAGES_FILE, msg_data)
        print('[Migrate] Backfilled status=queued to messages')
    
    overdue_count = process_overdue_queue()
    if overdue_count > 0:
        print(f'[Migrate] Flagged {overdue_count} messages as overdue')

    # 10. Living Writer: Initialise and Migrate
    os.makedirs(os.path.join(DATA_DIR, 'exports'), exist_ok=True)
    lw_data = read_json(LIVING_WRITER_FILE)
    if lw_data is None:
        lw_data = { "stories": [] }
        write_json(LIVING_WRITER_FILE, lw_data)
        print('[Migrate] Initialised living_writer.json')
    else:
        changed = False
        for s in lw_data.get("stories", []):
            if "current_stage" not in s:
                s["current_stage"] = 1
                changed = True
            if "stage_completion" not in s:
                s["stage_completion"] = {"1":False,"2":False,"3":False,"4":False,"5":False,"6":False,"7":False}
                changed = True
            if "draft_complete" not in s:
                s["draft_complete"] = False
                changed = True
            if "draft_complete_at" not in s:
                s["draft_complete_at"] = None
                changed = True
            if "stage1" not in s:
                s["stage1"] = { "concept_note": "", "devonthink_nudge_shown": False }
                changed = True
            if "stage2" not in s:
                s["stage2"] = { "characters": [], "thematic_values": "", "historical_catastrophe": None, "fragments": [], "world_rules": None, "leviathan_answers": {}, "story_genome": "", "world_of_story_doc": "" }
                changed = True
            if "stage3" not in s:
                s["stage3"] = { "arc_brainstorms": [], "selected_arc_index": None, "four_episode_loglines": [], "tsv_output": "" }
                changed = True
            if "stage4" not in s:
                s["stage4"] = { "treesheets_files": [] }
                changed = True
            if "stage5" not in s:
                s["stage5"] = { "treatment_scenes": [], "descriptionary": [] }
                changed = True
            if "stage6" not in s:
                s["stage6"] = { "narrative_summary": "", "anki_deck_exported": False, "reconstruction_sessions": [] }
                changed = True
            if "stage7" not in s:
                s["stage7"] = { "export_targets": [], "session_notes": "" }
                changed = True
        if changed:
            write_json(LIVING_WRITER_FILE, lw_data)
            print('[Migrate] Updated living_writer.json payload schema')


# ── Plugin loader ─────────────────────────────────────────────────────────────

_plugins = {}

def load_plugins():
    import sys
    sys.path.insert(0, BASE_DIR)
    plugins_pkg = os.path.join(BASE_DIR, 'plugins')
    for finder, name, _ in pkgutil.iter_modules([plugins_pkg]):
        try:
            module = importlib.import_module(f'plugins.{name}')
            if hasattr(module, 'PLUGIN_CLASS'):
                instance = module.PLUGIN_CLASS()
                _plugins[instance.name] = instance
        except Exception as e:
            print(f'[Indaba] Failed to load plugin "{name}": {e}')

def get_enabled_plugins():
    settings = read_json('settings.json') or {}
    enabled  = settings.get('plugins_enabled', {})
    return {k: v for k, v in _plugins.items() if enabled.get(k, True)}

# ── Deadline helpers ──────────────────────────────────────────────────────────

def deadline_info(deadline_str):
    if not deadline_str:
        return None, None
    try:
        dl    = date.fromisoformat(deadline_str)
        today = date.today()
        delta = (dl - today).days
        if delta < 0:
            return f'OVERDUE ({abs(delta)}d)', 'overdue'
        elif delta == 0:
            return 'Today', 'urgent'
        elif delta == 1:
            return 'Tomorrow', 'urgent'
        elif delta <= 4:
            return f'{delta} days', 'urgent'
        elif delta <= 10:
            return f'{delta} days', 'soon'
        else:
            return dl.strftime('%d %b'), 'ok'
    except ValueError:
        return deadline_str, 'ok'

# ── Posting log helpers ───────────────────────────────────────────────────────

POSTING_PLATFORMS = ['patreon', 'website', 'vip_group', 'wa_channel']

def _posting_streak(log, platform):
    """Count consecutive days (including today if checked) where platform was posted."""
    streak = 0
    d = date.today()
    while True:
        key = d.isoformat()
        if log.get(key, {}).get(platform, False):
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak

# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/api/dashboard')
def api_dashboard():
    projects     = read_json('projects.json')  or []
    settings     = read_json('settings.json')  or {}
    pipeline     = read_json('content_pipeline.json') or []
    measures_all = read_json('lead_measures.json') or {}
    month_key    = date.today().strftime('%Y-%m')
    measures     = measures_all.get(month_key, {
        'pitches_sent': 0, 'pitch_meetings': 0,
        'in_active_review': 0, 'patreon_leads': 0, 'follow_ups': 0
    })

    today_key = date.today().isoformat()
    daily_log = read_json('daily_log.json') or {}
    today_log = daily_log.get(today_key, {'commitment': '', 'session_notes': []})

    for p in projects:
        label, cls = deadline_info(p.get('deadline'))
        p['deadline_label']   = label
        p['deadline_urgency'] = cls

    def sort_key(p):
        return (p.get('priority', 4), p.get('deadline') or '9999-12-31')
    projects_sorted = sorted(projects, key=sort_key)

    now = datetime.now()
    window_end_str = settings.get('window_end', '11:30')
    try:
        wh, wm    = map(int, window_end_str.split(':'))
        wend      = now.replace(hour=wh, minute=wm, second=0, microsecond=0)
        remaining = wend - now
        if remaining.total_seconds() > 0:
            hrs  = int(remaining.total_seconds() // 3600)
            mins = int((remaining.total_seconds() % 3600) // 60)
            window_remaining = f'{hrs}h {mins}m'
            window_active    = True
        else:
            window_remaining = 'Window closed'
            window_active    = False
    except Exception:
        window_remaining = ''
        window_active    = True

    enabled_plugins = [
        {'name': p.name, 'label': p.label, 'description': p.description,
         'actions': p.get_ui_actions()}
        for p in get_enabled_plugins().values()
    ]

    # Inbox summary — purge expired then count urgent (< 24h)
    inbox = read_json(INBOX_FILE) or []
    now_iso = datetime.now().isoformat()
    inbox = [item for item in inbox if item.get('expires_at', '9999') > now_iso]
    tomorrow_iso = (datetime.now() + timedelta(hours=24)).isoformat()
    inbox_urgent = sum(1 for i in inbox if i.get('expires_at', '9999') < tomorrow_iso)

    # Dynamic constants
    consts = get_constants()
    zone_caps = consts['zone_caps']

    # Posting log — today's status and per-platform streaks
    posting_log = read_json(POSTING_LOG_FILE) or {}
    today_key_p = date.today().isoformat()
    posting_today = posting_log.get(today_key_p, {p: False for p in POSTING_PLATFORMS})
    posting_streaks = {p: _posting_streak(posting_log, p) for p in POSTING_PLATFORMS}

    # Zone priorities — one project per zone can hold the focus slot
    active_projects = [p for p in projects if not p.get('completed')]
    zone_priorities = {}
    for z in zone_caps:
        focus = next((p['id'] for p in active_projects
                      if p.get('energy_zone') == z and p.get('zone_priority')), None)
        zone_priorities[z] = focus

    return jsonify({
        'projects':         projects_sorted,
        'settings':         settings,
        'content_pipeline': pipeline,
        'lead_measures':    measures,
        'month_key':        month_key,
        'window_remaining': window_remaining,
        'window_active':    window_active,
        'plugins':          enabled_plugins,
        'today':            date.today().isoformat(),
        'weekday':          date.today().strftime('%A'),
        'today_log':        today_log,
        'inbox':            inbox,
        'inbox_urgent':     inbox_urgent,
        'posting_today':    posting_today,
        'posting_streaks':  posting_streaks,
        'zone_priorities':  zone_priorities,
        'caps': {
            'total_active':  len(active_projects),
            'total_cap':     consts['total_project_cap'],
            'zone_counts':   {z: sum(1 for p in active_projects if p.get('energy_zone') == z) for z in zone_caps},
            'zone_caps':     zone_caps,
            'inbox_count':   len(inbox),
            'inbox_max':     consts['inbox_max'],
            'dormant_count': len(read_json(DORMANT_FILE) or []),
            'dormant_max':   consts['dormant_max'],
        },
    })

@app.route('/api/hub/summary')
def api_hub_summary():
    # 1. To-Do Summary
    projects = read_json('projects.json') or []
    active_projects = [p for p in projects if not p.get('completed')]
    today = date.today()
    overdue_count = 0
    for p in active_projects:
        dl_str = p.get('deadline')
        if dl_str:
            try:
                if date.fromisoformat(dl_str) < today:
                    overdue_count += 1
            except (ValueError, TypeError):
                pass
    inbox = read_json(INBOX_FILE) or []
    
    # 2. Living Writer Summary
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    stories = lw_data.get("stories", [])
    furthest = max((s.get("current_stage", 1) for s in stories), default=0)
    
    # 3. Publishing Central Summary
    pipeline = read_json('content_pipeline.json') or []
    chapters_live = 0
    chapters_pending = 0
    for e in pipeline:
        is_live = any(e.get(f'{p}_status') == 'live' for p in ['vip_group', 'patreon', 'website', 'wa_channel'])
        is_pending = any(e.get(f'{p}_status') == 'pending' for p in ['vip_group', 'patreon', 'website', 'wa_channel'])
        if is_live: chapters_live += 1
        if is_pending: chapters_pending += 1

    # 4. Promotion Machine Summary
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    
    contacts = contacts_data.get("contacts", [])
    leads = leads_data.get("leads", [])
    messages = messages_data.get("messages", [])
    
    open_leads = [l for l in leads if l.get('stage') not in ['won', 'lost']]
    queued_messages = [m for m in messages if m.get('status') == 'queued']

    return jsonify({
        'todo': {
            'active_projects': len(active_projects),
            'inbox_count': len(inbox),
            'overdue_projects': overdue_count
        },
        'living_writer': {
            'stories_in_pipeline': len(stories),
            'furthest_stage': furthest,
            'draft_complete_count': sum(1 for s in stories if s.get("draft_complete", False))
        },
        'publishing_central': {
            'chapters_live': chapters_live,
            'chapters_pending': chapters_pending
        },
        'promotion_machine': {
            'contacts_count': len(contacts),
            'open_leads': len(open_leads),
            'messages_queued': len(queued_messages)
        }
    })

# ── Projects ──────────────────────────────────────────────────────────────────

@app.route('/api/projects', methods=['GET'])
def get_projects():
    return jsonify(read_json('projects.json') or [])

@app.route('/api/projects', methods=['POST'])
def create_project():
    data     = request.get_json()
    projects = read_json('projects.json') or []
    now      = datetime.now().isoformat()
    project  = {
        'id':                  str(uuid.uuid4()),
        'name':                data.get('name', 'Untitled'),
        'type':                data.get('type', 'other'),
        'pipeline':            data.get('pipeline', 'creative_development'),
        'phase':               data.get('phase', ''),
        'phases':              data.get('phases', []),
        'next_action':         data.get('next_action', ''),
        'deadline':            data.get('deadline'),
        'blocked':             data.get('blocked', False),
        'blocked_reason':      data.get('blocked_reason'),
        'priority':            int(data.get('priority', 3)),
        'money_attached':      data.get('money_attached', False),
        'notes':               data.get('notes', ''),
        'source':              data.get('source', ''),
        'living_writer_record': data.get('living_writer_record', False),
        'crm_record':          data.get('crm_record', False),
        'mission_critical':    data.get('mission_critical', False),
        'energy_zone':         data.get('energy_zone', 'flexible'),
        'completed':           False,
        'completed_at':        None,
        'last_session_note':   '',
        'last_session_at':     None,
        'gw_lifecycle': {
            'commission_confirmed': False,
            'draft_delivered':      False,
            'revision_complete':    False,
            'final_delivered':      False,
            'invoice_sent':         False,
            'payment_received':     False,
        },
        'created_at':  now,
        'updated_at':  now,
    }
    projects.append(project)
    write_json('projects.json', projects)
    return jsonify(project), 201

@app.route('/api/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    data     = request.get_json()
    projects = read_json('projects.json') or []
    for i, p in enumerate(projects):
        if p['id'] == project_id:
            # Handle completed/completed_at logic
            if 'completed' in data:
                if data['completed'] != p.get('completed', False):
                    if data['completed']:
                        data['completed_at'] = datetime.now().isoformat()
                    else:
                        data['completed_at'] = None
            data['id']         = project_id
            data['created_at'] = p.get('created_at')
            data['updated_at'] = datetime.now().isoformat()
            projects[i]        = {**p, **data}
            write_json('projects.json', projects)
            return jsonify(projects[i])
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    projects = read_json('projects.json') or []
    projects = [p for p in projects if p['id'] != project_id]
    write_json('projects.json', projects)
    return jsonify({'ok': True})

@app.route('/api/projects/<project_id>/session-note', methods=['POST'])
def log_session_note(project_id):
    data     = request.get_json()
    note     = data.get('note', '').strip()
    projects = read_json('projects.json') or []
    for i, p in enumerate(projects):
        if p['id'] == project_id:
            projects[i]['last_session_note'] = note
            projects[i]['last_session_at']   = datetime.now().isoformat()
            projects[i]['updated_at']         = datetime.now().isoformat()
            write_json('projects.json', projects)
            # Also append to daily log
            today_key = date.today().isoformat()
            daily_log = read_json('daily_log.json') or {}
            entry     = daily_log.get(today_key, {'commitment': '', 'session_notes': []})
            entry.setdefault('session_notes', []).append({
                'project_id':   project_id,
                'project_name': p.get('name', ''),
                'note':         note,
                'at':           projects[i]['last_session_at'],
            })
            daily_log[today_key] = entry
            write_json('daily_log.json', daily_log)
            return jsonify(projects[i])
    return jsonify({'error': 'Not found'}), 404

# ── Daily log ─────────────────────────────────────────────────────────────────

@app.route('/api/daily-log', methods=['GET'])
def get_daily_log():
    date_key  = request.args.get('date', date.today().isoformat())
    daily_log = read_json('daily_log.json') or {}
    return jsonify(daily_log.get(date_key, {'commitment': '', 'session_notes': []}))

@app.route('/api/daily-log', methods=['PUT'])
def update_daily_log():
    data      = request.get_json()
    date_key  = data.get('date', date.today().isoformat())
    daily_log = read_json('daily_log.json') or {}
    entry     = daily_log.get(date_key, {'commitment': '', 'session_notes': []})
    if 'commitment' in data:
        entry['commitment'] = data['commitment']
    daily_log[date_key] = entry
    write_json('daily_log.json', daily_log)
    return jsonify(entry)

# ── Settings ──────────────────────────────────────────────────────────────────

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(read_json('settings.json') or {})

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    data     = request.get_json()
    settings = read_json('settings.json') or {}
    settings.update(data)
    write_json('settings.json', settings)
    return jsonify(settings)

# ── Lead Measures ─────────────────────────────────────────────────────────────

@app.route('/api/lead-measures', methods=['GET'])
def get_lead_measures():
    all_measures = read_json('lead_measures.json') or {}
    month_key    = date.today().strftime('%Y-%m')
    return jsonify(all_measures.get(month_key, {}))

@app.route('/api/lead-measures', methods=['PUT'])
def update_lead_measures():
    data         = request.get_json()
    all_measures = read_json('lead_measures.json') or {}
    month_key    = date.today().strftime('%Y-%m')
    current      = all_measures.get(month_key, {
        'pitches_sent': 0, 'pitch_meetings': 0,
        'in_active_review': 0, 'patreon_leads': 0, 'follow_ups': 0
    })
    for k, v in data.items():
        if str(v) == '+1':
            current[k] = current.get(k, 0) + 1
        elif str(v) == '-1':
            current[k] = max(0, current.get(k, 0) - 1)
        else:
            current[k] = int(v)
    all_measures[month_key] = current
    write_json('lead_measures.json', all_measures)
    return jsonify(current)

# ── Content Pipeline ──────────────────────────────────────────────────────────

@app.route('/api/content-pipeline', methods=['GET'])
def get_content_pipeline():
    return jsonify(read_json('content_pipeline.json') or [])

@app.route('/api/content-pipeline', methods=['POST'])
def add_pipeline_entry():
    data     = request.get_json()
    pipeline = read_json('content_pipeline.json') or []
    entry = {
        'id':               str(uuid.uuid4()),
        'chapter':          data.get('chapter', ''),
        'vip_group_status': data.get('vip_group_status', 'not_started'),
        'patreon_status':   data.get('patreon_status', 'not_started'),
        'website_status':   data.get('website_status', 'not_started'),
        'wa_channel_status': data.get('wa_channel_status', 'not_started'),
        'assets':           data.get('assets', {}),
        'notes':            data.get('notes', ''),
    }
    pipeline.append(entry)
    write_json('content_pipeline.json', pipeline)
    return jsonify(entry), 201

@app.route('/api/content-pipeline/<entry_id>', methods=['PUT'])
def update_pipeline_entry(entry_id):
    data     = request.get_json()
    pipeline = read_json('content_pipeline.json') or []
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            pipeline[i] = {**e, **data, 'id': entry_id}
            write_json('content_pipeline.json', pipeline)
            return jsonify(pipeline[i])
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/content-pipeline/<entry_id>/increment-revision', methods=['POST'])
def increment_revision(entry_id):
    data = request.get_json() or {}
    field = data.get('field', 'revision')
    delta = data.get('delta', 1)
    pipeline = read_json('content_pipeline.json') or []
    for i, e in enumerate(pipeline):
        if e['id'] == entry_id:
            if field not in e:
                e[field] = 0
            e[field] = e.get(field, 0) + delta
            pipeline[i] = e
            write_json('content_pipeline.json', pipeline)
            return jsonify(pipeline[i])
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/content-pipeline/<entry_id>', methods=['DELETE'])
def delete_pipeline_entry(entry_id):
    pipeline = read_json('content_pipeline.json') or []
    pipeline = [e for e in pipeline if e['id'] != entry_id]
    write_json('content_pipeline.json', pipeline)
    return jsonify({'ok': True})

# ── Inbox ─────────────────────────────────────────────────────────────────────

def _purge_inbox():
    """Remove expired items and return the live inbox list."""
    inbox   = read_json(INBOX_FILE) or []
    now_iso = datetime.now().isoformat()
    live    = [item for item in inbox if item.get('expires_at', '9999') > now_iso]
    if len(live) < len(inbox):
        write_json(INBOX_FILE, live)
    return live

@app.route('/api/inbox', methods=['GET'])
def get_inbox():
    return jsonify(_purge_inbox())

@app.route('/api/inbox', methods=['POST'])
def create_inbox_item():
    inbox = _purge_inbox()
    if len(inbox) >= INBOX_MAX:
        return jsonify({'error': f'Inbox is full ({INBOX_MAX} items). Triage something before adding more.'}), 409
    data  = request.get_json()
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    captured = datetime.now()
    item = {
        'id':          str(uuid.uuid4())[:8],
        'title':       title,
        'notes':       (data.get('notes') or '').strip(),
        'captured_at': captured.isoformat(),
        'expires_at':  (captured + timedelta(days=INBOX_EXPIRY_DAYS)).isoformat(),
    }
    inbox.append(item)
    write_json(INBOX_FILE, inbox)
    return jsonify(item), 201

@app.route('/api/inbox/<item_id>', methods=['DELETE'])
def delete_inbox_item(item_id):
    inbox = read_json(INBOX_FILE) or []
    write_json(INBOX_FILE, [i for i in inbox if i['id'] != item_id])
    return jsonify({'ok': True})

@app.route('/api/inbox/<item_id>/archive', methods=['POST'])
def archive_inbox_item(item_id):
    inbox   = _purge_inbox()
    dormant = read_json(DORMANT_FILE) or []
    if len(dormant) >= DORMANT_MAX:
        return jsonify({'error': f'Dormant archive is full ({DORMANT_MAX} ideas). Delete something first.'}), 409
    item = next((i for i in inbox if i['id'] == item_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    dormant.append({
        'id':                   item['id'],
        'title':                item['title'],
        'notes':                item.get('notes', ''),
        'archived_at':          datetime.now().isoformat(),
        'original_captured_at': item.get('captured_at', ''),
    })
    write_json(DORMANT_FILE, dormant)
    write_json(INBOX_FILE, [i for i in inbox if i['id'] != item_id])
    return jsonify({'ok': True})

@app.route('/api/inbox/<item_id>/promote', methods=['POST'])
def promote_inbox_item(item_id):
    inbox    = _purge_inbox()
    projects = read_json('projects.json') or []
    item     = next((i for i in inbox if i['id'] == item_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    data        = request.get_json() or {}
    energy_zone = data.get('energy_zone', 'paid_work')
    active      = [p for p in projects if not p.get('completed')]
    consts      = get_constants()
    if len(active) >= consts['total_project_cap']:
        return jsonify({'error': f'Project cap reached ({consts["total_project_cap"]} active). Complete or remove one first.'}), 409
    zone_count = sum(1 for p in active if p.get('energy_zone') == energy_zone)
    zone_cap   = consts['zone_caps'].get(energy_zone, 99)
    if zone_count >= zone_cap:
        label = energy_zone.replace('_', ' ').title()
        return jsonify({'error': f'{label} zone is full ({zone_cap} projects). Complete or move one first.'}), 409
    now     = datetime.now().isoformat()
    project = {
        'id':                  str(uuid.uuid4()),
        'name':                data.get('name', item['title']),
        'type':                data.get('type', 'other'),
        'pipeline':            data.get('pipeline', 'creative_development'),
        'phase':               data.get('phase', ''),
        'phases':              [],
        'next_action':         data.get('next_action', ''),
        'deadline':            data.get('deadline'),
        'blocked':             False,
        'blocked_reason':      None,
        'priority':            int(data.get('priority', 3)),
        'money_attached':      data.get('money_attached', False),
        'notes':               item.get('notes', ''),
        'source':              'inbox',
        'living_writer_record': False,
        'crm_record':          False,
        'mission_critical':    data.get('mission_critical', False),
        'energy_zone':         energy_zone,
        'completed':           False,
        'completed_at':        None,
        'last_session_note':   '',
        'last_session_at':     None,
        'gw_lifecycle': {
            'commission_confirmed': False, 'draft_delivered': False,
            'revision_complete': False, 'final_delivered': False,
            'invoice_sent': False, 'payment_received': False,
        },
        'created_at':  now,
        'updated_at':  now,
    }
    projects.append(project)
    write_json('projects.json', projects)
    write_json(INBOX_FILE, [i for i in inbox if i['id'] != item_id])
    return jsonify(project), 201

# ── Dormant ───────────────────────────────────────────────────────────────────

@app.route('/api/dormant', methods=['GET'])
def get_dormant():
    return jsonify(read_json(DORMANT_FILE) or [])

@app.route('/api/dormant/<item_id>', methods=['DELETE'])
def delete_dormant_item(item_id):
    dormant = read_json(DORMANT_FILE) or []
    write_json(DORMANT_FILE, [i for i in dormant if i['id'] != item_id])
    return jsonify({'ok': True})

@app.route('/api/dormant/<item_id>/revive', methods=['POST'])
def revive_dormant_item(item_id):
    dormant = read_json(DORMANT_FILE) or []
    inbox   = _purge_inbox()
    if len(inbox) >= INBOX_MAX:
        return jsonify({'error': f'Inbox full ({INBOX_MAX} items). Triage first.'}), 409
    item = next((i for i in dormant if i['id'] == item_id), None)
    if not item:
        return jsonify({'error': 'Not found'}), 404
    captured = datetime.now()
    inbox.append({
        'id':          item['id'],
        'title':       item['title'],
        'notes':       item.get('notes', ''),
        'captured_at': captured.isoformat(),
        'expires_at':  (captured + timedelta(days=INBOX_EXPIRY_DAYS)).isoformat(),
    })
    write_json(INBOX_FILE, inbox)
    write_json(DORMANT_FILE, [i for i in dormant if i['id'] != item_id])
    return jsonify({'ok': True})

@app.route('/api/caps', methods=['GET'])
def get_caps():
    projects = read_json('projects.json') or []
    active   = [p for p in projects if not p.get('completed')]
    inbox    = _purge_inbox()
    dormant  = read_json(DORMANT_FILE) or []
    consts   = get_constants()
    return jsonify({
        'total_active':  len(active),
        'total_cap':     consts['total_project_cap'],
        'zone_counts':   {z: sum(1 for p in active if p.get('energy_zone') == z) for z in consts['zone_caps']},
        'zone_caps':     consts['zone_caps'],
        'inbox_count':   len(inbox),
        'inbox_max':     consts['inbox_max'],
        'dormant_count': len(dormant),
        'dormant_max':   consts['dormant_max'],
    })

# ── Settings — triage question ─────────────────────────────────────────────────

@app.route('/api/settings/triage-question', methods=['GET'])
def get_triage_question():
    s = read_json('settings.json') or {}
    return jsonify({'question': s.get('inbox_triage_question',
        'If you had one more year of productive work left, would you spend any of it on this?')})

@app.route('/api/settings/triage-question', methods=['PUT'])
def update_triage_question():
    data = request.get_json()
    s    = read_json('settings.json') or {}
    s['inbox_triage_question'] = data.get('question', '')
    write_json('settings.json', s)
    return jsonify({'ok': True})

# ── Zone Priority ─────────────────────────────────────────────────────────────

@app.route('/api/projects/<project_id>/set-zone-priority', methods=['POST'])
def set_zone_priority(project_id):
    projects = read_json('projects.json') or []
    target = next((p for p in projects if p['id'] == project_id), None)
    if not target:
        return jsonify({'error': 'Not found'}), 404
    if target.get('completed'):
        return jsonify({'error': 'Cannot set focus on a completed project'}), 400
    zone = target.get('energy_zone', 'paid_work')
    # Check if another project in this zone already holds focus
    existing = next((p for p in projects
                     if p['id'] != project_id
                     and p.get('energy_zone') == zone
                     and p.get('zone_priority')
                     and not p.get('completed')), None)
    if existing:
        return jsonify({
            'error': f'"{existing["name"]}" already holds focus for this zone. Release it first.',
            'conflict_id': existing['id'],
            'conflict_name': existing['name'],
        }), 409
    # Set this project as zone priority
    for p in projects:
        if p['id'] == project_id:
            p['zone_priority'] = True
            p['updated_at'] = datetime.now().isoformat()
    write_json('projects.json', projects)
    return jsonify({'ok': True})

@app.route('/api/projects/<project_id>/release-zone-priority', methods=['POST'])
def release_zone_priority(project_id):
    projects = read_json('projects.json') or []
    for p in projects:
        if p['id'] == project_id:
            p['zone_priority'] = False
            p['updated_at'] = datetime.now().isoformat()
            write_json('projects.json', projects)
            return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

# ── Posting Log ───────────────────────────────────────────────────────────────

@app.route('/api/posting-log', methods=['GET'])
def get_posting_log():
    date_key = request.args.get('date', date.today().isoformat())
    log = read_json(POSTING_LOG_FILE) or {}
    entry = log.get(date_key, {p: False for p in POSTING_PLATFORMS})
    streaks = {p: _posting_streak(log, p) for p in POSTING_PLATFORMS}
    return jsonify({'date': date_key, 'posting': entry, 'streaks': streaks})

@app.route('/api/posting-log/toggle', methods=['POST'])
def toggle_posting():
    data     = request.get_json()
    platform = data.get('platform')
    date_key = data.get('date', date.today().isoformat())
    if platform not in POSTING_PLATFORMS:
        return jsonify({'error': f'Unknown platform: {platform}'}), 400
    log   = read_json(POSTING_LOG_FILE) or {}
    entry = log.get(date_key, {p: False for p in POSTING_PLATFORMS})
    entry[platform] = not entry.get(platform, False)
    log[date_key] = entry
    write_json(POSTING_LOG_FILE, log)
    streaks = {p: _posting_streak(log, p) for p in POSTING_PLATFORMS}
    return jsonify({'date': date_key, 'posting': entry, 'streaks': streaks})

# ── Settings: editable constants ──────────────────────────────────────────────

@app.route('/api/settings/constants', methods=['GET'])
def get_settings_constants():
    return jsonify(get_constants())

@app.route('/api/settings/constants', methods=['PUT'])
def update_settings_constants():
    data = request.get_json()
    s    = read_json('settings.json') or {}
    allowed = set(_DEFAULTS.keys())
    for k, v in data.items():
        if k in allowed:
            try:
                s[k] = int(v)
            except (ValueError, TypeError):
                return jsonify({'error': f'Invalid value for {k}: must be integer'}), 400
    write_json('settings.json', s)
    return jsonify(get_constants())

# ── Notes ─────────────────────────────────────────────────────────────────────

@app.route('/api/notes', methods=['GET'])
def list_notes():
    os.makedirs(NOTES_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(NOTES_DIR, '*.md')),
                   key=os.path.getmtime, reverse=True)
    notes = []
    for f in files:
        name  = os.path.basename(f)
        mtime = datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
        with open(f, 'r', encoding='utf-8') as fh:
            first = fh.readline().strip().lstrip('#').strip()
        notes.append({'filename': name, 'title': first or name, 'modified': mtime})
    return jsonify(notes)

@app.route('/api/notes', methods=['POST'])
def create_note():
    data    = request.get_json()
    title   = data.get('title', 'Untitled').strip()
    content = data.get('content', '').strip()
    os.makedirs(NOTES_DIR, exist_ok=True)
    slug     = ''.join(c if c.isalnum() or c in '-_ ' else '' for c in title)
    slug     = slug.strip().replace(' ', '-').lower()[:40] or 'note'
    ts       = datetime.now().strftime('%Y%m%d-%H%M')
    filename = f'{ts}-{slug}.md'
    path     = os.path.join(NOTES_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'# {title}\n\n{content}')
    return jsonify({'filename': filename, 'title': title}), 201

@app.route('/api/notes/<filename>', methods=['GET'])
def read_note(filename):
    filename = os.path.basename(filename)
    path     = os.path.join(NOTES_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'filename': filename, 'content': content})

@app.route('/api/notes/<filename>', methods=['PUT'])
def update_note(filename):
    filename = os.path.basename(filename)
    path     = os.path.join(NOTES_DIR, filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Not found'}), 404
    content  = request.get_json().get('content', '')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return jsonify({'ok': True})

@app.route('/api/notes/<filename>', methods=['DELETE'])
def delete_note(filename):
    filename = os.path.basename(filename)
    path     = os.path.join(NOTES_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({'ok': True})

# ── PROMOTION MACHINE: CONTACTS ──

@app.route('/api/promo/contacts', methods=['GET'])
def list_promo_contacts():
    data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    return jsonify(data)

@app.route('/api/promo/contacts', methods=['POST'])
def create_promo_contact():
    data = request.get_json()
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    
    if not name:
        return jsonify({"error": "name is required"}), 400
    
    # E.164 pattern: ^\+\d{7,15}$
    if not phone or not re.match(r'^\+\d{7,15}$', phone):
        return jsonify({"error": "Phone must be in E.164 format, e.g. +27821234567"}), 400
        
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contacts = contacts_data.get("contacts", [])
    
    if any(c.get('phone') == phone for c in contacts):
        return jsonify({"error": "A contact with this phone number already exists"}), 409
        
    now = datetime.utcnow().isoformat() + "Z"
    new_contact = {
        "id": str(uuid.uuid4()),
        "name": name,
        "phone": phone,
        "email": data.get('email', ''),
        "tags": data.get('tags', []),
        "source": data.get('source', 'manual'),
        "notes": data.get('notes', ''),
        "created_at": now,
        "updated_at": now
    }
    contacts.append(new_contact)
    write_json(PROMO_CONTACTS_FILE, contacts_data)
    return jsonify(new_contact), 201

@app.route('/api/promo/contacts/import_csv', methods=['POST'])
def import_contacts_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    if not file.filename.lower().endswith('.csv'):
        return jsonify({"error": "File must be a .csv"}), 400
        
    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    reader = csv.DictReader(stream)
    
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    existing_phones = {c.get('phone') for c in contacts_data.get("contacts", [])}
    
    imported = 0
    skipped_invalid = 0
    skipped_duplicate = 0
    
    now = datetime.utcnow().isoformat() + "Z"
    
    for row in reader:
        name = row.get('name', '').strip()
        phone = row.get('phone', '').strip()
        
        if not name or not phone or not re.match(r'^\+\d{7,15}$', phone):
            skipped_invalid += 1
            continue
            
        if phone in existing_phones:
            skipped_duplicate += 1
            continue
            
        email = row.get('email', '')
        tags_raw = row.get('tags', '')
        tags = [t.strip() for t in tags_raw.split(';')] if tags_raw else []
        
        new_contact = {
            "id": str(uuid.uuid4()),
            "name": name,
            "phone": phone,
            "email": email,
            "tags": tags,
            "source": "csv",
            "notes": "",
            "created_at": now,
            "updated_at": now
        }
        contacts_data["contacts"].append(new_contact)
        existing_phones.add(phone)
        imported += 1
        
    if imported > 0:
        write_json(PROMO_CONTACTS_FILE, contacts_data)
        
    return jsonify({
        "imported": imported,
        "skipped_invalid": skipped_invalid,
        "skipped_duplicate": skipped_duplicate
    })

@app.route('/api/promo/contacts/<contact_id>', methods=['GET'])
def get_promo_contact(contact_id):
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact = next((c for c in contacts_data.get("contacts", []) if c['id'] == contact_id), None)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
        
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    contact_leads = [l for l in leads_data.get("leads", []) if l['contact_id'] == contact_id]
    
    return jsonify({"contact": contact, "leads": contact_leads})

@app.route('/api/promo/contacts/<contact_id>', methods=['PUT'])
def update_promo_contact(contact_id):
    data = request.get_json()
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contacts = contacts_data.get("contacts", [])
    
    contact_idx = next((i for i, c in enumerate(contacts) if c['id'] == contact_id), None)
    if contact_idx is None:
        return jsonify({"error": "Contact not found"}), 404
        
    contact = contacts[contact_idx]
    
    if 'phone' in data:
        new_phone = data['phone'].strip()
        if not re.match(r'^\+\d{7,15}$', new_phone):
            return jsonify({"error": "Phone must be in E.164 format, e.g. +27821234567"}), 400
        
        if new_phone != contact['phone']:
            if any(c.get('phone') == new_phone for c in contacts if c['id'] != contact_id):
                return jsonify({"error": "A contact with this phone number already exists"}), 409
            contact['phone'] = new_phone

    # Fields to merge
    for field in ['name', 'email', 'tags', 'source', 'notes']:
        if field in data:
            contact[field] = data[field]
            
    contact['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_CONTACTS_FILE, contacts_data)
    return jsonify(contact)

@app.route('/api/promo/contacts/<contact_id>', methods=['DELETE'])
def delete_promo_contact(contact_id):
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contacts = contacts_data.get("contacts", [])
    contact = next((c for c in contacts if c['id'] == contact_id), None)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
        
    phone = contact['phone']
    contacts_data["contacts"] = [c for c in contacts if c['id'] != contact_id]
    write_json(PROMO_CONTACTS_FILE, contacts_data)
    
    # Cascade delete leads
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads_data["leads"] = [l for l in leads_data.get("leads", []) if l['contact_id'] != contact_id]
    write_json(PROMO_LEADS_FILE, leads_data)
    
    # Update queued messages
    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    changed_ms = False
    for m in messages_data.get("messages", []):
        if m.get("status") == "queued" and m.get("recipient_phone") == phone:
            m["recipient_name"] = "[Deleted]"
            changed_ms = True
    if changed_ms:
        write_json(PROMO_MESSAGES_FILE, messages_data)
        
    return jsonify({"ok": true})

@app.route('/api/promo/contacts/<contact_id>/tags', methods=['POST'])
def update_contact_tags(contact_id):
    data = request.get_json()
    tags = data.get('tags')
    if not isinstance(tags, list):
        return jsonify({"error": "tags must be an array"}), 400
        
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact = next((c for c in contacts_data.get("contacts", []) if c['id'] == contact_id), None)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
        
    contact['tags'] = tags
    contact['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_CONTACTS_FILE, contacts_data)
    return jsonify(contact)

@app.route('/api/promo/contacts/by_tag/<tag>', methods=['GET'])
def list_contacts_by_tag(tag):
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    tag_lower = tag.lower()
    filtered = [
        c for c in contacts_data.get("contacts", [])
        if any(t.lower() == tag_lower for t in c.get('tags', []))
    ]
    return jsonify({"contacts": filtered})

# ── PROMOTION MACHINE: LEADS ──

LEAD_STAGES = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]

@app.route('/api/promo/leads', methods=['GET'])
def list_promo_leads():
    contact_id = request.args.get('contact_id')
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads = leads_data.get("leads", [])
    if contact_id:
        leads = [l for l in leads if l['contact_id'] == contact_id]
    return jsonify({"leads": leads})

@app.route('/api/promo/leads', methods=['POST'])
def create_promo_lead():
    data = request.get_json()
    contact_id = data.get('contact_id')
    product = data.get('product')
    product_type = data.get('product_type')
    
    if not all([contact_id, product, product_type]):
        return jsonify({"error": "contact_id, product, and product_type are required"}), 400
        
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact = next((c for c in contacts_data.get("contacts", []) if c['id'] == contact_id), None)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
        
    # Check max leads per contact
    settings = read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS
    max_leads = settings.get("max_leads_per_contact", 10)
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    current_leads = [l for l in leads_data.get("leads", []) if l['contact_id'] == contact_id]
    if len(current_leads) >= max_leads:
        return jsonify({"error": f"Contact exceeds max leads limit ({max_leads})"}), 409
        
    now = datetime.utcnow().isoformat() + "Z"
    new_lead = {
        "id": str(uuid.uuid4()),
        "contact_id": contact_id,
        "contact_name": contact['name'],
        "product": product,
        "product_type": product_type,
        "stage": "lead",
        "notes": data.get('notes', ''),
        "communication_log": [],
        "created_at": now,
        "updated_at": now
    }
    leads_data["leads"].append(new_lead)
    write_json(PROMO_LEADS_FILE, leads_data)
    return jsonify(new_lead), 201

@app.route('/api/promo/leads/<lead_id>', methods=['GET'])
def get_promo_lead(lead_id):
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    lead = next((l for l in leads_data.get("leads", []) if l['id'] == lead_id), None)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    return jsonify(lead)

@app.route('/api/promo/leads/<lead_id>', methods=['PUT'])
def update_promo_lead(lead_id):
    data = request.get_json()
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads = leads_data.get("leads", [])
    
    lead_idx = next((i for i, l in enumerate(leads) if l['id'] == lead_id), None)
    if lead_idx is None:
        return jsonify({"error": "Lead not found"}), 404
        
    lead = leads[lead_idx]
    
    if 'stage' in data:
        if data['stage'] not in LEAD_STAGES:
            return jsonify({"error": f"Invalid stage. Must be one of {LEAD_STAGES}"}), 400
        lead['stage'] = data['stage']
        
    for field in ['notes', 'product', 'product_type']:
        if field in data:
            lead[field] = data[field]
            
    lead['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_LEADS_FILE, leads_data)
    return jsonify(lead)

@app.route('/api/promo/leads/<lead_id>', methods=['DELETE'])
def delete_promo_lead(lead_id):
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads = leads_data.get("leads", [])
    if not any(l['id'] == lead_id for l in leads):
        return jsonify({"error": "Lead not found"}), 404
        
    leads_data["leads"] = [l for l in leads if l['id'] != lead_id]
    write_json(PROMO_LEADS_FILE, leads_data)
    return jsonify({"ok": True})

@app.route('/api/promo/leads/<lead_id>/log_communication', methods=['POST'])
def log_lead_communication(lead_id):
    data = request.get_json()
    msg_text = data.get('message')
    direction = data.get('direction') # inbound | outbound
    
    if not msg_text or direction not in ['inbound', 'outbound']:
        return jsonify({"error": "message and valid direction (inbound/outbound) required"}), 400
        
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    lead = next((l for l in leads_data.get("leads", []) if l['id'] == lead_id), None)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
        
    entry = {
        "id": str(uuid.uuid4()),
        "direction": direction,
        "message": msg_text,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    lead.setdefault("communication_log", []).append(entry)
    lead["updated_at"] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_LEADS_FILE, leads_data)
    return jsonify(entry)

@app.route('/api/promo/leads/<lead_id>/ai_suggest', methods=['POST'])
def ai_suggest_lead_message(lead_id):
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    lead = next((l for l in leads_data.get("leads", []) if l['id'] == lead_id), None)
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
        
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    contact = next((c for c in contacts_data.get("contacts", []) if c['id'] == lead['contact_id']), None)
    
    history = lead.get("communication_log", [])[-5:] # Last 5 messages
    history_str = "\n".join([f"{m['direction']}: {m['message']}" for m in history])
    
    prompt = f"""Target Contact: {contact['name'] if contact else 'Prospect'}
Product: {lead['product']} (Type: {lead['product_type']})
Current Sales Stage: {lead['stage']}

Recent Communication History:
{history_str if history_str else "No prior communication logged."}

Task: Suggest the next outbound message to advance this lead to the next stage.
Keep it personal, professional, and very brief. South African context.
Return ONLY the suggested message text."""

    try:
        suggestion = call_ai("crm_assist", [{"role": "user", "content": prompt}])
        return jsonify({"suggestion": suggestion.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    except Exception as e:
        return jsonify({"error": str(e)}), 502

# ── PROMOTION MACHINE: MESSAGE MAKER ──

@app.route('/api/promo/message_maker/generate', methods=['POST'])
def generate_promo_message():
    data = request.get_json()
    purpose = data.get('purpose', '').strip()
    if not purpose:
        return jsonify({"error": "purpose is required"}), 400
        
    event_name = data.get('event_name', '')
    event_date = data.get('event_date', '')
    target_audience = data.get('target_audience', '')
    tone_notes = data.get('tone_notes', '')
    recipient_name = data.get('recipient_name', '')
    
    user_prompt = f"""Purpose: {purpose}
Event Name: {event_name}
Event Date: {event_date}
Target Audience: {target_audience}
Tone Notes: {tone_notes}
Recipient Name: {recipient_name}"""

    system_content = MESSAGE_MAKER_SYSTEM_PROMPT.format(purpose=purpose)
    
    try:
        message = call_ai("message_maker", [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt}
        ])
        return jsonify({"message": message.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    except Exception as e:
        return jsonify({"error": str(e)}), 502

# ── PROMOTION MACHINE: BOOK SERIALIZER ──

@app.route('/api/promo/books', methods=['GET'])
def list_promo_books():
    data = read_json(PROMO_BOOKS_FILE) or {"books": []}
    return jsonify(data)

@app.route('/api/promo/books', methods=['POST'])
def create_promo_book():
    data = request.get_json()
    title = data.get('title', '').strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
        
    books_data = read_json(PROMO_BOOKS_FILE) or {"books": []}
    now = datetime.utcnow().isoformat() + "Z"
    new_book = {
        "id": str(uuid.uuid4()),
        "title": title,
        "author": data.get('author', ''),
        "patreon_url": data.get('patreon_url', ''),
        "website_url": data.get('website_url', ''),
        "chunks": [],
        "created_at": now,
        "updated_at": now
    }
    books_data["books"].append(new_book)
    write_json(PROMO_BOOKS_FILE, books_data)
    return jsonify(new_book), 201

@app.route('/api/promo/books/<book_id>', methods=['GET'])
def get_promo_book(book_id):
    books_data = read_json(PROMO_BOOKS_FILE) or {"books": []}
    book = next((b for b in books_data.get("books", []) if b['id'] == book_id), None)
    if not book:
        return jsonify({"error": "Book not found"}), 404
    return jsonify(book)

@app.route('/api/promo/books/<book_id>', methods=['PUT'])
def update_promo_book(book_id):
    data = request.get_json()
    books_data = read_json(PROMO_BOOKS_FILE) or {"books": []}
    books = books_data.get("books", [])
    
    book_idx = next((i for i, b in enumerate(books) if b['id'] == book_id), None)
    if book_idx is None:
        return jsonify({"error": "Book not found"}), 404
        
    book = books[book_idx]
    for field in ['title', 'author', 'patreon_url', 'website_url']:
        if field in data:
            book[field] = data[field]
            
    book['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_BOOKS_FILE, books_data)
    return jsonify(book)

@app.route('/api/promo/books/<book_id>', methods=['DELETE'])
def delete_promo_book(book_id):
    books_data = read_json(PROMO_BOOKS_FILE) or {"books": []}
    books = books_data.get("books", [])
    if not any(b['id'] == book_id for b in books):
        return jsonify({"error": "Book not found"}), 404
        
    books_data["books"] = [b for b in books if b['id'] != book_id]
    write_json(PROMO_BOOKS_FILE, books_data)
    return jsonify({"ok": True})

@app.route('/api/promo/books/<book_id>/ingest', methods=['POST'])
def ingest_book_content(book_id):
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "Input text is empty."}), 400
        
    books_data = read_json(PROMO_BOOKS_FILE) or {"books": []}
    book = next((b for b in books_data.get("books", []) if b['id'] == book_id), None)
    if not book:
        return jsonify({"error": "Book not found"}), 404
        
    settings = read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS
    target_words = settings.get("serializer_defaults", {}).get("target_chunk_word_count", 300)
    max_words = settings.get("serializer_defaults", {}).get("max_chunk_word_count", 400)
    branding = settings.get("wa_channel_branding", {})
    
    cta = f"\n\n{branding.get('cta_emoji', '👇')}\n{branding.get('cta_text', '')}"
    
    system_prompt = BOOK_SERIALIZER_SYSTEM_PROMPT.format(
        target_words=target_words,
        max_words=max_words,
        cta=cta
    )
    
    try:
        response_text = call_ai("book_serializer", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Text to serialize:\n\n{text}"}
        ])
        
        # Strip potential markdown code blocks
        clean_json = re.sub(r'^```json\s*|\s*```$', '', response_text.strip(), flags=re.MULTILINE)
        chunks_list = json.loads(clean_json)
        
        now = datetime.utcnow().isoformat() + "Z"
        new_chunks = []
        for c in chunks_list:
            chunk = {
                "id": str(uuid.uuid4()),
                "content": c.get("content", ""),
                "cliffhanger_note": c.get("cliffhanger_note", ""),
                "status": "pending",
                "word_count": len(c.get("content", "").split()),
                "created_at": now
            }
            new_chunks.append(chunk)
            
        book["chunks"].extend(new_chunks)
        book["updated_at"] = now
        write_json(PROMO_BOOKS_FILE, books_data)
        return jsonify({"chunks": new_chunks})
        
    except json.JSONDecodeError as e:
        return jsonify({"error": f"AI returned invalid JSON: {str(e)}", "raw": response_text}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.route('/api/promo/books/<book_id>/chunks/<chunk_id>/queue', methods=['POST'])
def queue_book_chunk(book_id, chunk_id):
    data = request.get_json() or {}
    scheduled_at = data.get('scheduled_at')
    
    books_data = read_json(PROMO_BOOKS_FILE) or {"books": []}
    book = next((b for b in books_data.get("books", []) if b['id'] == book_id), None)
    if not book:
        return jsonify({"error": "Book not found"}), 404
        
    chunk = next((c for c in book.get("chunks", []) if c['id'] == chunk_id), None)
    if not chunk:
        return jsonify({"error": "Chunk not found"}), 404
        
    if chunk.get("status") == "queued":
        return jsonify({"error": "This chunk is already in the send queue."}), 409
        
    # Create message queue entry
    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now = datetime.utcnow().isoformat() + "Z"
    
    new_message = {
        "id": str(uuid.uuid4()),
        "recipient_phone": "WA-CHANNEL", # Placeholder for target channel
        "recipient_name": "WhatsApp Channel",
        "content": chunk["content"],
        "status": "queued",
        "source": "book_serializer",
        "source_ref": {"book_id": book_id, "chunk_id": chunk_id},
        "scheduled_at": scheduled_at,
        "created_at": now,
        "updated_at": now
    }
    
    messages_data["messages"].append(new_message)
    write_json(PROMO_MESSAGES_FILE, messages_data)
    
    chunk["status"] = "queued"
    chunk["message_id"] = new_message["id"]
    write_json(PROMO_BOOKS_FILE, books_data)
    
    return jsonify(new_message)

    return jsonify(new_message)

# ── PROMOTION MACHINE: PROVERBS & WA POST MAKER ──

@app.route('/api/promo/proverbs', methods=['GET'])
def list_promo_proverbs():
    used_filter = request.args.get('used') # true | false
    data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverbs = data.get("proverbs", [])
    if used_filter:
        is_used = used_filter.lower() == 'true'
        proverbs = [p for p in proverbs if p.get('used', False) == is_used]
    return jsonify({"proverbs": proverbs})

@app.route('/api/promo/proverbs', methods=['POST'])
def add_promo_proverb():
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
        
    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    new_p = {
        "id": str(uuid.uuid4()),
        "text": text,
        "origin": data.get('origin', ''),
        "used": False,
        "used_at": None,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    proverbs_data["proverbs"].append(new_p)
    write_json(PROMO_PROVERBS_FILE, proverbs_data)
    return jsonify(new_p), 201

@app.route('/api/promo/proverbs/import_bulk', methods=['POST'])
def import_proverbs_bulk():
    data = request.get_json()
    ps = data.get('proverbs', [])
    if not isinstance(ps, list) or not ps:
        return jsonify({"error": "proverbs must be a non-empty array"}), 400
        
    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    imported = 0
    now = datetime.utcnow().isoformat() + "Z"
    for p in ps:
        text = p.get('text', '').strip()
        if text:
            new_p = {
                "id": str(uuid.uuid4()),
                "text": text,
                "origin": p.get('origin', ''),
                "used": False,
                "used_at": None,
                "created_at": now
            }
            proverbs_data["proverbs"].append(new_p)
            imported += 1
    if imported > 0:
        write_json(PROMO_PROVERBS_FILE, proverbs_data)
    return jsonify({"imported": imported})

@app.route('/api/promo/proverbs/export', methods=['GET'])
def export_proverbs_csv():
    data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverbs = data.get("proverbs", [])
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Text', 'Origin', 'Used', 'Used At', 'Created At'])
    
    for p in proverbs:
        writer.writerow([
            p.get('id'),
            p.get('text'),
            p.get('origin'),
            p.get('used'),
            p.get('used_at'),
            p.get('created_at')
        ])
        
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=proverbs_export.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/api/promo/wa_post/generate', methods=['POST'])
def generate_wa_post():
    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverbs = proverbs_data.get("proverbs", [])
    unused = [p for p in proverbs if not p.get('used', False)]
    if not unused:
        return jsonify({"error": "All proverbs have been used. Import more proverbs to continue."}), 409
        
    # Pick oldest unused
    proverb = unused[0]
    
    settings = read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS
    config = settings.get("ai_providers", {})
    
    # Check image gen config
    img_config = config.get("image_gen", {})
    if not img_config.get("endpoint"):
        return jsonify({"error": "Image generation provider not configured. Set it in Promotion Machine Settings."}), 503

    # Generate Meaning & Image Prompt
    system_prompt = "You are a South African culture expert and creative director."
    user_prompt = f"""Proverb: "{proverb['text']}" (Origin: {proverb['origin']})

1. Generate a brief meaning of this proverb (max 40 words).
2. Generate a visual image prompt for this proverb (max 60 words, no text in image).

Return a JSON object: {{"meaning": "...", "image_prompt": "..."}}"""

    try:
        raw_ai = call_ai("wa_post_maker", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        clean_json = re.sub(r'^```json\s*|\s*```$', '', raw_ai.strip(), flags=re.MULTILINE)
        result = json.loads(clean_json)
        
        meaning = result.get('meaning', '')
        img_prompt = result.get('image_prompt', '')
        
        # Call image generation API
        import requests
        img_resp = requests.post(
            img_config['endpoint'],
            json={"prompt": img_prompt},
            headers={"Authorization": f"Bearer {os.environ.get(img_config.get('api_key_env', ''))}"},
            timeout=30
        )
        if img_resp.status_code != 200:
            return jsonify({"error": f"Image generation failed: {img_resp.text}"}), 502
            
        img_url = img_resp.json().get('url')
        if not img_url:
            return jsonify({"error": f"Image generation returned no URL: {img_resp.text}"}), 502
            
        # Assemble final post content
        branding = settings.get("wa_channel_branding", {})
        cta = f"\n\n{branding.get('cta_emoji', '👇')}\n{branding.get('cta_text', '')}"
        
        post_content = f"{img_url}\n\n{proverb['text']}\n\n{meaning}{cta}"
        
        # Update proverb
        proverb['used'] = True
        proverb['used_at'] = datetime.utcnow().isoformat() + "Z"
        proverb['meaning'] = meaning
        proverb['image_prompt'] = img_prompt
        proverb['image_url'] = img_url
        proverb['post_content'] = post_content
        
        write_json(PROMO_PROVERBS_FILE, proverbs_data)
        
        return jsonify({
            "proverb_id": proverb['id'],
            "post_content": post_content,
            "image_url": img_url
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.route('/api/promo/wa_post/<proverb_id>/queue', methods=['POST'])
def queue_wa_post(proverb_id):
    data = request.get_json() or {}
    scheduled_at = data.get('scheduled_at')
    recipient_phone = data.get('recipient_phone', 'WA-CHANNEL')
    
    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverb = next((p for p in proverbs_data.get("proverbs", []) if p['id'] == proverb_id), None)
    if not proverb:
        return jsonify({"error": "Proverb not found"}), 404
        
    post_content = proverb.get('post_content')
    if not post_content:
        return jsonify({"error": "Post content not yet generated for this proverb."}), 409
        
    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now = datetime.utcnow().isoformat() + "Z"
    
    new_message = {
        "id": str(uuid.uuid4()),
        "recipient_phone": recipient_phone,
        "recipient_name": "WhatsApp Channel" if recipient_phone == "WA-CHANNEL" else "Contact",
        "content": post_content,
        "status": "queued",
        "source": "wa_post_maker",
        "source_ref": {"proverb_id": proverb_id},
        "scheduled_at": scheduled_at,
        "created_at": now,
        "updated_at": now
    }
    
    messages_data["messages"].append(new_message)
    write_json(PROMO_MESSAGES_FILE, messages_data)
    
    return jsonify(new_message)

# ── PROMOTION MACHINE: MESSAGE QUEUE & SENDER ──

def write_cowork_job(message):
    """Writes /data/cowork_jobs/{message_id}.json for Cowork."""
    try:
        job_dir = os.path.join(DATA_DIR, 'cowork_jobs')
        os.makedirs(job_dir, exist_ok=True)
        job_file = os.path.join(job_dir, f"{message['id']}.json")
        
        job_data = {
            "message_id": message["id"],
            "recipient_phone": message["recipient_phone"],
            "recipient_name": message["recipient_name"],
            "content": message["content"],
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(job_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error writing cowork job: {e}")
        return False

@app.route('/api/promo/messages', methods=['GET'])
def list_promo_messages():
    status = request.args.get('status')
    limit = int(request.args.get('limit', 50))
    data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msgs = data.get("messages", [])
    if status:
        msgs = [m for m in msgs if m.get('status') == status]
    
    # Sort by created_at desc
    msgs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify({"messages": msgs[:limit]})

@app.route('/api/promo/messages/<msg_id>', methods=['GET'])
def get_promo_message(msg_id):
    data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msg = next((m for m in data.get("messages", []) if m['id'] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
    return jsonify(msg)

@app.route('/api/promo/messages/<msg_id>', methods=['DELETE'])
def delete_promo_message(msg_id):
    data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msgs = data.get("messages", [])
    msg = next((m for m in msgs if m['id'] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
        
    if msg.get('status') not in ['queued', 'overdue']:
        return jsonify({"error": f"Cannot delete message with status: {msg.get('status')}"}), 409
        
    data["messages"] = [m for m in msgs if m['id'] != msg_id]
    write_json(PROMO_MESSAGES_FILE, data)
    return jsonify({"ok": True})

@app.route('/api/promo/messages/<msg_id>/reschedule', methods=['POST'])
def reschedule_promo_message(msg_id):
    data = request.get_json()
    new_time = data.get('scheduled_at')
    
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msgs = msgs_data.get("messages", [])
    msg = next((m for m in msgs if m['id'] == msg_id), None)
    if not msg:
        return jsonify({"error": "Message not found"}), 404
        
    if msg.get('status') == 'sent':
        return jsonify({"error": "Cannot reschedule a sent message"}), 409
        
    msg['scheduled_at'] = new_time
    msg['status'] = 'queued' # Return to queued if it was failed/overdue
    msg['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    return jsonify(msg)

@app.route('/api/promo/sender/process_queue', methods=['POST'])
def process_promo_queue():
    data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now = datetime.utcnow().isoformat() + "Z"
    dispatched = 0
    failed = 0
    
    for m in data["messages"]:
        if m.get("status") == "queued":
            # Check schedule if present
            sched = m.get("scheduled_at")
            if not sched or sched <= now:
                if write_cowork_job(m):
                    m["status"] = "dispatched"
                    m["updated_at"] = now
                    dispatched += 1
                else:
                    m["status"] = "failed"
                    m["updated_at"] = now
                    failed += 1
                    
    write_json(PROMO_MESSAGES_FILE, data)
    return jsonify({
        "dispatched": dispatched,
        "failed": failed,
        "instruction": "Trigger Cowork with: Send WhatsApps from Indaba"
    })

@app.route('/api/promo/sender/reconcile', methods=['POST'])
def reconcile_promo_results():
    results_dir = os.path.join(DATA_DIR, 'cowork_results')
    if not os.path.exists(results_dir):
        return jsonify({"reconciled": 0, "message": "No results found."})
        
    files = glob.glob(os.path.join(results_dir, "*.json"))
    if not files:
        return jsonify({"reconciled": 0, "message": "No results found."})
        
    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    leads_data = read_json(PROMO_LEADS_FILE) or {"leads": []}
    
    reconciled = 0
    sent_count = 0
    failed_count = 0
    
    now = datetime.utcnow().isoformat() + "Z"
    
    for f_path in files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                res = json.load(f)
            
            msg_id = res.get("message_id")
            status = res.get("status")
            
            # Find matching message
            msg = next((m for m in messages_data["messages"] if m["id"] == msg_id), None)
            if msg:
                if status == "sent":
                    msg["status"] = "sent"
                    msg["sent_at"] = res.get("sent_at", now)
                    msg["updated_at"] = now
                    sent_count += 1
                    
                    # Update lead log if applicable
                    lead_id = msg.get("lead_id")
                    if lead_id:
                        lead = next((l for l in leads_data["leads"] if l["id"] == lead_id), None)
                        if lead:
                            if "communication_log" not in lead:
                                lead["communication_log"] = []
                            lead["communication_log"].append({
                                "id": str(uuid.uuid4()),
                                "timestamp": now,
                                "direction": "outbound",
                                "channel": "whatsapp",
                                "message": msg["content"],
                                "message_id": msg["id"]
                            })
                elif status == "failed":
                    msg["status"] = "failed"
                    msg["updated_at"] = now
                    failed_count += 1
                
                reconciled += 1
            
            # Delete result file
            os.remove(f_path)
        except Exception as e:
            print(f"Error processing result file {f_path}: {e}")
            
    if reconciled > 0:
        write_json(PROMO_MESSAGES_FILE, messages_data)
        write_json(PROMO_LEADS_FILE, leads_data)
        
    return jsonify({
        "reconciled": reconciled,
        "sent": sent_count,
        "failed": failed_count
    })

@app.route('/api/promo/sender/send_now', methods=['POST'])
def promo_send_now():
    data = request.json
    if not data or 'message_id' not in data:
        return jsonify({"error": "message_id missing"}), 400
        
    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    msg_id = data['message_id']
    msg = next((m for m in messages_data["messages"] if m["id"] == msg_id), None)
    
    if not msg:
        return jsonify({"error": "Message not found"}), 404
        
    if msg.get("status") != "queued":
        return jsonify({"error": "Only queued messages can be dispatched"}), 409
        
    if write_cowork_job(msg):
        msg["status"] = "dispatched"
        msg["updated_at"] = datetime.utcnow().isoformat() + "Z"
        write_json(PROMO_MESSAGES_FILE, messages_data)
        return jsonify({
            "ok": True,
            "instruction": "Trigger Cowork with: Send WhatsApps from Indaba"
        })
    else:
        msg["status"] = "failed"
        msg["updated_at"] = datetime.utcnow().isoformat() + "Z"
        write_json(PROMO_MESSAGES_FILE, messages_data)
        return jsonify({"ok": False, "error": "Failed to write job file"})

@app.route('/api/promo/messages/bulk', methods=['POST'])
def create_bulk_messages():
    data = request.get_json()
    tag = data.get('tag')
    content = data.get('content', '')
    scheduled_at = data.get('scheduled_at')
    
    if not tag or not content:
        return jsonify({"error": "tag and content are required"}), 400
        
    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    tag_lower = tag.lower()
    targets = [
        c for c in contacts_data.get("contacts", [])
        if any(t.lower() == tag_lower for t in c.get('tags', []))
    ]
    
    if not targets:
        return jsonify({"error": f"No contacts found with tag: {tag}"}), 404
        
    batch_id = str(uuid.uuid4())
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now = datetime.utcnow().isoformat() + "Z"
    
    created = []
    for c in targets:
        # Substitute {name}
        msg_content = content.replace("{name}", c['name'])
        new_msg = {
            "id": str(uuid.uuid4()),
            "recipient_phone": c['phone'],
            "recipient_name": c['name'],
            "content": msg_content,
            "status": "queued",
            "source": data.get('source', 'manual'),
            "bulk_batch_id": batch_id,
            "scheduled_at": scheduled_at,
            "created_at": now,
            "updated_at": now
        }
        msgs_data["messages"].append(new_msg)
        created.append({"name": c['name'], "phone": c['phone']})
        
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    return jsonify({
        "batch_id": batch_id,
        "message_count": len(created),
        "contacts": created
    })

@app.route('/api/promo/messages/bulk/<batch_id>', methods=['GET'])
def get_bulk_batch(batch_id):
    data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    batch_msgs = [m for m in data.get("messages", []) if m.get('bulk_batch_id') == batch_id]
    return jsonify({"messages": batch_msgs})

@app.route('/api/promo/messages/single', methods=['POST'])
def send_single_message():
    data = request.get_json()
    phone = data.get('recipient_phone')
    name = data.get('recipient_name', 'Contact')
    content = data.get('content')
    scheduled_at = data.get('scheduled_at')
    lead_id = data.get('lead_id')
    
    if not phone or not content:
        return jsonify({"error": "recipient_phone and content are required"}), 400
        
    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now = datetime.utcnow().isoformat() + "Z"
    
    msg_id = str(uuid.uuid4())
    new_message = {
        "id": msg_id,
        "recipient_phone": phone,
        "recipient_name": name,
        "content": content,
        "status": "queued",
        "source": "manual_single",
        "source_ref": {"lead_id": lead_id} if lead_id else {},
        "scheduled_at": scheduled_at,
        "created_at": now,
        "updated_at": now
    }
    
    if not scheduled_at:
        # Send now
        if write_cowork_job(new_message):
            new_message['status'] = 'dispatched'
        else:
            new_message['status'] = 'failed'
            new_message['error'] = 'Failed to write job file'
    
    messages_data["messages"].append(new_message)
    write_json(PROMO_MESSAGES_FILE, messages_data)
    
    return jsonify({
        "message_id": msg_id,
        "status": new_message['status'],
        "error": new_message.get('error')
    }), 201

# ── PROMOTION MACHINE: SETTINGS ──

@app.route('/api/promo/settings', methods=['GET'])
def get_promo_settings():
    return jsonify(read_json(PROMO_SETTINGS_FILE) or DEFAULT_PROMO_SETTINGS)

@app.route('/api/promo/settings', methods=['PUT'])
def update_promo_settings():
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Settings must be a JSON object"}), 400
    write_json(PROMO_SETTINGS_FILE, data)
    return jsonify(data)

    write_json(PROMO_SETTINGS_FILE, data)
    return jsonify(data)

# ── Earnings ──────────────────────────────────────────────────────────────────

EARNINGS_FILE = 'earnings.json'

@app.route('/api/earnings', methods=['GET'])
def list_earnings():
    earnings = read_json(EARNINGS_FILE) or []
    return jsonify(earnings)

@app.route('/api/earnings', methods=['POST'])
def create_earning():
    data = request.get_json()
    if not data or 'date' not in data or 'platform' not in data or 'amount' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    earnings = read_json(EARNINGS_FILE) or []
    entry = {
        'id': str(uuid.uuid4())[:8],
        'date': data['date'],
        'platform': data['platform'],
        'amount': float(data['amount']),
        'notes': data.get('notes', '')
    }
    earnings.append(entry)
    write_json(EARNINGS_FILE, earnings)
    return jsonify(entry), 201

@app.route('/api/earnings/<entry_id>', methods=['DELETE'])
def delete_earning(entry_id):
    earnings = read_json(EARNINGS_FILE) or []
    filtered = [e for e in earnings if e.get('id') != entry_id]
    if len(filtered) == len(earnings):
        return jsonify({'error': 'Not found'}), 404
    write_json(EARNINGS_FILE, filtered)
    return jsonify({'ok': True})

@app.route('/api/earnings/monthly', methods=['GET'])
def monthly_earnings():
    earnings = read_json(EARNINGS_FILE) or []
    monthly = {}
    for e in earnings:
        month = e['date'][:7]  # YYYY-MM
        monthly[month] = monthly.get(month, 0) + e['amount']
    # Convert to list of {month, total}
    result = [{'month': m, 'total': round(t, 2)} for m, t in monthly.items()]
    result.sort(key=lambda x: x['month'], reverse=True)
    return jsonify(result)

# ── Plugins ───────────────────────────────────────────────────────────────────

@app.route('/api/plugins', methods=['GET'])
def list_plugins():
    settings = read_json('settings.json') or {}
    enabled  = settings.get('plugins_enabled', {})
    return jsonify([{
        'name': p.name, 'label': p.label, 'description': p.description,
        'enabled': enabled.get(p.name, True), 'actions': p.get_ui_actions(),
    } for p in _plugins.values()])

@app.route('/api/plugins/<plugin_name>/execute', methods=['POST'])
def execute_plugin(plugin_name):
    if plugin_name not in _plugins:
        return jsonify({'error': f'Plugin "{plugin_name}" not found'}), 404
    plugin  = _plugins[plugin_name]
    payload = request.get_json() or {}
    data = {
        'projects':         read_json('projects.json') or [],
        'content_pipeline': read_json('content_pipeline.json') or [],
        'lead_measures':    read_json('lead_measures.json') or {},
        'settings':         read_json('settings.json') or {},
        'params':           payload.get('params', {}),
    }
    try:
        result = plugin.execute(payload.get('action'), data)
        return jsonify({'ok': True, 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Serve frontend ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)


# ── LIVING WRITER ──

@app.route('/api/lw/stories', methods=['GET'])
def get_lw_stories():
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    return jsonify({"stories": lw_data.get("stories", [])})

@app.route('/api/lw/stories', methods=['POST'])
def create_lw_story():
    data = request.get_json() or {}
    title = data.get('title')
    if not title or not title.strip():
        return jsonify({"error": "title is required"}), 400
        
    settings = read_json('settings.json') or {}
    lw_max_stories = settings.get('lw_max_stories', 20)
    
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    if len(lw_data.get("stories", [])) >= lw_max_stories:
        return jsonify({"error": "Maximum number of stories in pipeline reached"}), 409
        
    now = datetime.utcnow().isoformat() + "Z"
    new_story = {
        "id": str(uuid.uuid4()),
        "title": title.strip(),
        "created_at": now,
        "updated_at": now,
        "current_stage": 1,
        "stage_completion": {"1":False,"2":False,"3":False,"4":False,"5":False,"6":False,"7":False},
        "draft_complete": False,
        "draft_complete_at": None,
        "stage1": { "concept_note": "", "devonthink_nudge_shown": False },
        "stage2": { "characters": [], "thematic_values": "", "historical_catastrophe": None, "fragments": [], "world_rules": None, "leviathan_answers": {}, "story_genome": "", "world_of_story_doc": "" },
        "stage3": { "arc_brainstorms": [], "selected_arc_index": None, "four_episode_loglines": [], "tsv_output": "" },
        "stage4": { "treesheets_files": [] },
        "stage5": { "treatment_scenes": [], "descriptionary": [] },
        "stage6": { "narrative_summary": "", "anki_deck_exported": False, "reconstruction_sessions": [] },
        "stage7": { "export_targets": [], "session_notes": "" }
    }
    lw_data["stories"].append(new_story)
    write_json(LIVING_WRITER_FILE, lw_data)
    return jsonify(new_story), 201

@app.route('/api/lw/stories/<story_id>', methods=['GET'])
def get_lw_story(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
    return jsonify(story)

@app.route('/api/lw/stories/<story_id>', methods=['PUT'])
def update_lw_story(story_id):
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    data.pop('id', None)
    data.pop('created_at', None)
    
    def deep_update(d, u):
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                deep_update(d[k], v)
            else:
                d[k] = v
                
    deep_update(story, data)
    story['updated_at'] = datetime.utcnow().isoformat() + "Z"
    
    write_json(LIVING_WRITER_FILE, lw_data)
    return jsonify(story)

@app.route('/api/lw/stories/<story_id>', methods=['DELETE'])
def delete_lw_story(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    stories = lw_data.get("stories", [])
    if not any(s['id'] == story_id for s in stories):
        return jsonify({"error": "Story not found"}), 404
        
    lw_data["stories"] = [s for s in stories if s['id'] != story_id]
    write_json(LIVING_WRITER_FILE, lw_data)
    return jsonify({"ok": True})

@app.route('/api/lw/stories/<story_id>/advance', methods=['POST'])
def advance_lw_story(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    stage = story.get('current_stage', 1)
    if stage >= 7:
        return jsonify({"error": "Story is already at the final stage"}), 409
        
    if stage == 2:
        chars = story.get('stage2', {}).get('characters', [])
        if len(chars) < 2:
            return jsonify({"error": "Stage 2 requires at least 2 Character Arc Outlines before advancing"}), 409
    elif stage == 5:
        scenes = story.get('stage5', {}).get('treatment_scenes', [])
        if len(scenes) == 0:
            return jsonify({"error": "Add at least one treatment scene before advancing from Stage 5"}), 409
            
    story['stage_completion'][str(stage)] = True
    story['current_stage'] = stage + 1
    story['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(LIVING_WRITER_FILE, lw_data)
    return jsonify(story)

@app.route('/api/lw/stories/<story_id>/complete', methods=['POST'])
def complete_lw_story(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    if story.get('current_stage', 1) < 7:
        return jsonify({"error": "Story must reach Stage 7 before marking draft complete"}), 409
        
    now = datetime.utcnow().isoformat() + "Z"
    story['draft_complete'] = True
    story['draft_complete_at'] = now
    story['stage_completion']["7"] = True
    story['updated_at'] = now
    write_json(LIVING_WRITER_FILE, lw_data)
    
    projects = read_json('projects.json') or []
    for p in projects:
        if p.get('name') == story.get('title') and p.get('pipeline') == "Creative Development":
            p['phase'] = "Draft Complete"
            if 'session_notes' in p:
                if p['session_notes']:
                    p['session_notes'] += f"\n\nLivingWriter: draft-complete signal received at {now}"
                else:
                    p['session_notes'] = f"LivingWriter: draft-complete signal received at {now}"
            write_json('projects.json', projects)
            print(f"[LivingWriter] Marked project '{p['name']}' as draft-complete")
            break
            
    return jsonify(story)

@app.route('/api/lw/stories/<story_id>/cruxes', methods=['GET'])
def get_lw_story_cruxes(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    scenes = story.get('stage5', {}).get('treatment_scenes', [])
    try:
        scenes = sorted(scenes, key=lambda x: int(x.get('order', 0)))
    except (TypeError, ValueError):
        pass
        
    res = [{"order": s.get('order', 0), "slug_line": s.get('slug_line', ''), "crux": s.get('crux', '')} for s in scenes]
    return jsonify(res)

@app.route('/api/lw/stories/<story_id>/stage4/open_file', methods=['POST'])
def open_lw_stage4_file(story_id):
    data = request.get_json() or {}
    filepath = data.get('filepath')
    if not filepath or not filepath.strip():
        return jsonify({"error": "filepath is required"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    import subprocess, sys
    try:
        if sys.platform == "darwin":
            subprocess.call(["open", filepath])
        elif sys.platform == "win32":
            os.startfile(filepath)
        else:
            subprocess.call(["xdg-open", filepath])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": "Could not open file. Check that the path is correct and the file exists."}), 500

@app.route('/api/lw/stories/<story_id>/stage2/derive_thematic_values', methods=['POST'])
def derive_thematic_values(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    chars = story.get('stage2', {}).get('characters', [])
    if len(chars) < 2:
        return jsonify({"error": "Add at least 2 characters before deriving thematic values"}), 400
        
    char_lines = []
    for c in chars:
        name = c.get('name', 'Character N')
        crucible = c.get('crucible', '')
        char_lines.append(f"Character: {name}\nCrucible: {crucible}")
    char_str = "\n\n".join(char_lines)
    
    messages = [
        {"role": "system", "content": "You are a story development assistant helping a writer identify the dominant thematic tensions in their story. Return only plain prose, no bullet points, no headers, no markdown. Maximum 300 words."},
        {"role": "user", "content": f"Here are the character crucibles from my story:\n{char_str}\nIdentify the 2-3 dominant value tensions that emerge across these characters. For each tension write one paragraph (max 100 words) describing what this world does to people who choose one value over the other. Write in present tense. Be specific and concrete, not abstract."}
    ]
    
    try:
        res_text = call_ai("lw_ai", messages, max_tokens=600)
        return jsonify({"thematic_values": res_text})
    except Exception as e:
        return jsonify({"error": "AI provider unavailable", "detail": str(e)}), 502

@app.route('/api/lw/stories/<story_id>/stage3/arc_brainstorm', methods=['POST'])
def generate_arc_brainstorm(story_id):
    data = request.get_json() or {}
    char_id = data.get('character_id')
    if not char_id:
        return jsonify({"error": "character_id is required"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    char = next((c for c in story.get('stage2', {}).get('characters', []) if c.get('id') == char_id), None)
    if not char:
        return jsonify({"error": "Character not found"}), 404
        
    genome = story.get('stage2', {}).get('story_genome', '')[:500]
    
    sys_msg = "You are a story structure expert using Lewis Jorstad's Integrated Inner and Outer Journey framework from Mastering Character Arcs. Return only valid JSON, no markdown, no explanation."
    user_msg = f"Character data:\nOne line: {char.get('character_in_one_line', '')}\nWound: {char.get('wound', '')}\nLie: {char.get('lie', '')}\nCrucible: {char.get('crucible', '')}\nTerrain: {char.get('terrain', '')}\nTransformation: {char.get('transformation', '')}\nWhat they leave behind: {char.get('what_they_leave_behind', '')}\nStory world context: {genome}\n\nGenerate 3 distinct arc possibilities. Return a JSON array of exactly 3 objects. Each object must have these keys: primary_arc_type (Positive, Negative, or Flat), primary_arc_rationale (string), secondary_arc_type (string), secondary_arc_explanation (string), lie (string), truth (string), core_wound (string), arc_summary (string, max 5 sentences of max 15 words each), editorial_recommendation (string)"
    
    try:
        res_text = call_ai("lw_ai", [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], max_tokens=2000)
        if res_text.startswith("```json"):
            res_text = res_text[7:].strip()
            if res_text.endswith("```"):
                res_text = res_text[:-3].strip()
        parsed = json.loads(res_text)
        if not isinstance(parsed, list):
            raise ValueError("Expected an array")
            
        new_bs = []
        for p in parsed:
            bs = {
                "id": str(uuid.uuid4()),
                "character_id": char_id,
                "primary_arc_type": p.get("primary_arc_type"),
                "primary_arc_rationale": p.get("primary_arc_rationale"),
                "secondary_arc_type": p.get("secondary_arc_type"),
                "secondary_arc_explanation": p.get("secondary_arc_explanation"),
                "lie": p.get("lie"),
                "truth": p.get("truth"),
                "core_wound": p.get("core_wound"),
                "arc_summary": p.get("arc_summary"),
                "editorial_recommendation": p.get("editorial_recommendation")
            }
            new_bs.append(bs)
            story['stage3']['arc_brainstorms'].append(bs)
            
        story['updated_at'] = datetime.utcnow().isoformat() + "Z"
        write_json(LIVING_WRITER_FILE, lw_data)
        return jsonify({"brainstorms": new_bs})
    except Exception as e:
        return jsonify({"error": "AI returned invalid format. Try again.", "detail": str(e)}), 502

@app.route('/api/lw/stories/<story_id>/stage3/generate_loglines', methods=['POST'])
def generate_loglines(story_id):
    data = request.get_json() or {}
    bs_id = data.get('brainstorm_id')
    if not bs_id:
        return jsonify({"error": "brainstorm_id is required"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    bs = next((b for b in story.get('stage3', {}).get('arc_brainstorms', []) if b.get('id') == bs_id), None)
    if not bs:
        return jsonify({"error": "Brainstorm not found"}), 404
        
    sys_msg = "You are a story structure expert. Return only valid JSON, no markdown, no explanation."
    user_msg = f"Arc data:\nPrimary arc: {bs.get('primary_arc_type')} — {bs.get('primary_arc_rationale')}\nSecondary arc: {bs.get('secondary_arc_type')}\nThe lie: {bs.get('lie')}\nThe truth: {bs.get('truth')}\nArc summary: {bs.get('arc_summary')}\n\nGenerate exactly 4 act-level loglines using Lewis Jorstad's Integrated Inner and Outer Journey framework.\nRules:\n- Exactly 25 words each\n- Present tense, third person\n- Each logline weaves inner transformation and outer plot conflict simultaneously\n- Together they trace: Catalyst, Turning Point, Regression, Choice\n\nReturn a JSON array of exactly 4 objects. Each object:\n{{ 'act': 'Act 1' or 'Act 2 Part 1' or 'Act 2 Part 2' or 'Act 3', 'logline': 'exactly 25 words' }}"
    
    try:
        res_text = call_ai("lw_ai", [{"role":"system","content":sys_msg},{"role":"user","content":user_msg}], max_tokens=800)
        if res_text.startswith("```json"):
            res_text = res_text[7:].strip()
            if res_text.endswith("```"):
                res_text = res_text[:-3].strip()
        parsed = json.loads(res_text)
        if not isinstance(parsed, list) or len(parsed) != 4:
            raise ValueError("Expected an array of length 4")
            
        story['stage3']['four_episode_loglines'] = parsed
        tsv_output = "Act\tLogline\n" + "\n".join([f"{p.get('act')}\t{p.get('logline')}" for p in parsed])
        story['stage3']['tsv_output'] = tsv_output
        story['updated_at'] = datetime.utcnow().isoformat() + "Z"
        write_json(LIVING_WRITER_FILE, lw_data)
        return jsonify({"loglines": parsed, "tsv_output": tsv_output})
    except Exception as e:
        return jsonify({"error": "AI returned invalid format. Try again.", "detail": str(e)}), 502

@app.route('/api/lw/stories/<story_id>/stage2/leviathan_assist', methods=['POST'])
def leviathan_assist(story_id):
    data = request.get_json() or {}
    q_id = data.get('question_id')
    if not q_id:
        return jsonify({"error": "question_id is required"}), 400
        
    q_def = next((q for q in LEVIATHAN_QUESTIONS if q['id'] == q_id), None)
    if not q_def:
        return jsonify({"error": "Invalid question_id"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    curr_answer = story.get('stage2', {}).get('leviathan_answers', {}).get(q_id, "")
    
    genome_context = []
    stage2 = story.get('stage2', {})
    for ref in q_def.get('genome_refs', []):
        if ref == 'characters':
            chars = stage2.get('characters', [])
            cl = [f"{c.get('name')}: {c.get('character_in_one_line')}" for c in chars]
            genome_context.append("Characters:\n" + "\n".join(cl))
        else:
            val = stage2.get(ref)
            if val:
                genome_context.append(f"{ref}: {val}")
                
    g_str = "\n\n".join(genome_context)
    
    sys_msg = "You are a worldbuilding assistant helping a writer develop their story world. Be specific and concrete. Draw only from the writer's own established material. Maximum 200 words."
    user_msg = f"Question: {q_def['question']}\nRelevant story material:\n{g_str}\nCurrent answer (may be empty): {curr_answer}\nSuggest a specific, concrete answer to this question that is consistent with the established material. Also flag any contradictions between the current answer and established material. Return JSON:\n{{ 'suggestion': 'string', 'contradictions': ['string'] }}"
    
    try:
        res_text = call_ai("lw_ai", [{"role":"system","content":sys_msg},{"role":"user","content":user_msg}], max_tokens=400)
        if res_text.startswith("```json"):
            res_text = res_text[7:].strip()
            if res_text.endswith("```"):
                res_text = res_text[:-3].strip()
        parsed = json.loads(res_text)
        return jsonify({"suggestion": parsed.get("suggestion", ""), "contradictions": parsed.get("contradictions", [])})
    except Exception as e:
        return jsonify({"error": "AI returned invalid format.", "detail": str(e)}), 502

@app.route('/api/lw/stories/<story_id>/stage6/export_anki', methods=['POST'])
def export_anki(story_id):
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    scenes = story.get('stage5', {}).get('treatment_scenes', [])
    if not scenes:
        return jsonify({"error": "No treatment scenes found. Complete Stage 5 before exporting."}), 400
        
    try:
        import genanki
    except ImportError:
        return jsonify({"error": "genanki is required. Run: pip install genanki"}), 500
        
    h = 0
    for c in story_id:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    
    model_id = h
    deck_id = h ^ 0x12345678
    
    my_model = genanki.Model(
      model_id,
      'LivingWriter Model',
      fields=[
        {'name': 'Front'},
        {'name': 'Back'},
      ],
      templates=[
        {
          'name': 'Card 1',
          'qfmt': '{{Front}}',
          'afmt': '{{FrontSide}}<hr id="answer">{{Back}}',
        },
      ])
      
    my_deck = genanki.Deck(deck_id, f"LivingWriter: {story.get('title')}")
    
    for s in scenes:
        front = f"{s.get('slug_line')} — What is the crux of this scene?"
        back = s.get('crux', '')
        my_deck.add_note(genanki.Note(model=my_model, fields=[front, back]))
        
    for d in story.get('stage5', {}).get('descriptionary', []):
        front = f"Describe: {d.get('header', '')}"
        back = d.get('body', '')
        my_deck.add_note(genanki.Note(model=my_model, fields=[front, back]))
        
    filename = f"{story_id}_anki.apkg"
    filepath = os.path.join(DATA_DIR, 'exports', filename)
    genanki.Package(my_deck).write_to_file(filepath)
    
    story['stage6']['anki_deck_exported'] = True
    story['updated_at'] = datetime.utcnow().isoformat() + "Z"
    write_json(LIVING_WRITER_FILE, lw_data)
    
    return jsonify({"download_url": f"/api/lw/exports/{filename}"})

@app.route('/api/lw/exports/<filename>')
def download_lw_export(filename):
    filepath = os.path.join(DATA_DIR, 'exports', filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(os.path.join(DATA_DIR, 'exports'), filename)

@app.route('/api/lw/stories/<story_id>/stage7/export', methods=['POST'])
def export_lw_story(story_id):
    data = request.get_json() or {}
    target = data.get('target')
    fmt = data.get('format')
    
    if target not in ["final_draft","scrivener","novelwriter","ulysses","freewrite"]:
        return jsonify({"error": "Invalid export target"}), 400
    if fmt not in ["treatment","cruxes"]:
        return jsonify({"error": "format must be treatment or cruxes"}), 400
        
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    story = next((s for s in lw_data.get("stories", []) if s['id'] == story_id), None)
    if not story:
        return jsonify({"error": "Story not found"}), 404
        
    scenes = story.get('stage5', {}).get('treatment_scenes', [])
    try:
        scenes = sorted(scenes, key=lambda x: int(x.get('order', 0)))
    except (TypeError, ValueError):
        pass
        
    if fmt == "cruxes":
        content = "\n\n".join([f"{s.get('slug_line', '')}\n{s.get('crux', '')}" for s in scenes])
        filename = f"{story_id}_cruxes.txt"
    else:
        content = "\n\n".join([f"{s.get('slug_line', '')}\n{s.get('crux', '')}\n{s.get('scene_description', '')}" for s in scenes])
        filename = f"{story_id}_treatment.txt"
        
    filepath = os.path.join(DATA_DIR, 'exports', filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return jsonify({"download_url": f"/api/lw/exports/{filename}"})

@app.route('/api/lw/leviathan/questions')
def get_leviathan_questions():
    return jsonify({"questions": LEVIATHAN_QUESTIONS})

if __name__ == '__main__':
    import socket, webbrowser, threading

    def find_free_port(preferred=5050, max_tries=20):
        for port in range(preferred, preferred + max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('', port))
                    return port
                except OSError:
                    continue
        raise RuntimeError(f'No free port found in range {preferred}–{preferred + max_tries}')

    load_plugins()
    migrate()

    port = find_free_port(5050)
    url  = f'http://localhost:{port}'

    print('\n  ┌──────────────────────────────────┐')
    print('  │   INDABA — Morning Briefing       │')
    print(f'  │   {url:<30}│')
    print('  └──────────────────────────────────┘')

    if port != 5050:
        print(f'\n  ⚠  Port 5050 was busy — running on port {port} instead.\n')
    else:
        print()

    # Open the browser after a short delay so Flask is ready
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    app.run(host='0.0.0.0', port=port, debug=False)
