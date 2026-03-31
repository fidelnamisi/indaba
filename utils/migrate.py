"""
Startup migrations and data sync for Indaba.
Runs once on startup to ensure data model consistency.
"""
import os
import uuid
from copy import deepcopy
from datetime import datetime

from utils.json_store import read_json, write_json, DATA_DIR
from utils.constants import (
    PROMO_CONTACTS_FILE, PROMO_LEADS_FILE, PROMO_MESSAGES_FILE,
    PROMO_PROVERBS_FILE, PROMO_WORKS_FILE, PROMO_SETTINGS_FILE,
    LIVING_WRITER_FILE, CONTENT_PIPELINE_FILE,
    PROMO_MODULES_FILE, PROMO_ASSETS_FILE, DEFAULT_PROMO_SETTINGS
)
from utils.helpers import process_overdue_queue


def migrate():
    """Apply data model migrations on startup."""

    # 1. Projects: add completed fields
    projects = read_json('projects.json') or []
    changed  = False
    for p in projects:
        if 'completed' not in p:
            p['completed']    = False
            changed = True
        if 'completed_at' not in p:
            p['completed_at'] = None
            changed = True
    if changed:
        write_json('projects.json', projects)
        print('[Migrate] Added completed fields to projects')

    # 2. Projects: add phases field
    projects = read_json('projects.json') or []
    changed  = False
    for p in projects:
        if 'phases' not in p:
            p['phases'] = []
            changed = True
    if changed:
        write_json('projects.json', projects)
        print('[Migrate] Added phases field to projects')

    # 3. Settings: convert phase_templates strings to arrays
    settings = read_json('settings.json') or {}
    pt       = settings.get('phase_templates', {})
    changed  = False
    for k, v in pt.items():
        if isinstance(v, str):
            pt[k]   = [v]
            changed = True
    if changed:
        settings['phase_templates'] = pt
        write_json('settings.json', settings)
        print('[Migrate] Converted phase_templates strings to arrays')

    # 4. Projects: add mission_critical and energy_zone fields
    projects = read_json('projects.json') or []
    changed  = False
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
    changed  = False
    for p in projects:
        if p.get('energy_zone') == 'flexible':
            p['energy_zone'] = 'paid_work'
            changed = True
    if changed:
        write_json('projects.json', projects)
        print('[Migrate] Renamed energy_zone flexible → paid_work')

    # 6. Purge expired inbox items
    from utils.constants import INBOX_FILE
    inbox       = read_json(INBOX_FILE) or []
    now_iso     = datetime.now().isoformat()
    orig_count  = len(inbox)
    inbox       = [item for item in inbox if item.get('expires_at', '9999') > now_iso]
    if len(inbox) < orig_count:
        write_json(INBOX_FILE, inbox)
        print(f'[Migrate] Purged {orig_count - len(inbox)} expired inbox item(s)')

    # 7. Projects: add zone_priority field
    projects = read_json('projects.json') or []
    changed  = False
    for p in projects:
        if 'zone_priority' not in p:
            p['zone_priority'] = False
            changed = True
    if changed:
        write_json('projects.json', projects)
        print('[Migrate] Added zone_priority field to projects')

    # 8. Content pipeline: add revision fields
    pipeline = read_json('content_pipeline.json') or []
    changed  = False
    for e in pipeline:
        if 'revision' not in e:
            e['revision'] = 1
            changed = True
        for platform in ('vip_group', 'patreon', 'website', 'wa_channel'):
            key = f'{platform}_revision'
            if key not in e:
                e[key]  = 0
                changed = True
    if changed:
        write_json('content_pipeline.json', pipeline)
        print('[Migrate] Added revision fields to pipeline entries')

    # 9. Ensure required directories
    os.makedirs(os.path.join(DATA_DIR, 'cowork_jobs'),   exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'cowork_results'), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, 'exports'),        exist_ok=True)

    promo_init = [
        (PROMO_CONTACTS_FILE, {"contacts": []}),
        (PROMO_LEADS_FILE,    {"leads": []}),
        (PROMO_MESSAGES_FILE, {"messages": []}),
        (PROMO_PROVERBS_FILE, {"proverbs": []}),
        (PROMO_WORKS_FILE,    {"works": []}),
        (PROMO_SETTINGS_FILE, deepcopy(DEFAULT_PROMO_SETTINGS)),
        (LIVING_WRITER_FILE,  {"stories": []}),
    ]
    for filename, default_data in promo_init:
        if not os.path.exists(os.path.join(DATA_DIR, filename)):
            write_json(filename, default_data)
            print(f'[Migrate] Initialised {filename}')

    # 10. Proverbs: add queue_status field
    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    prov_changed  = False
    for p in proverbs_data["proverbs"]:
        if "queue_status" not in p:
            if p.get("used") and p.get("composite_path"):
                p["queue_status"] = "sent"
            elif p.get("composite_path"):
                p["queue_status"] = "pending"
            else:
                p["queue_status"] = None
            prov_changed = True
    if prov_changed:
        write_json(PROMO_PROVERBS_FILE, proverbs_data)
        print("[Migrate] Added queue_status to proverbs")

    # 11. Messages: backfill status and check overdue
    msg_data    = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
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

    # 12. Leads: add value field (entity_id removed — entities concept deprecated)
    leads_data_mig = read_json(PROMO_LEADS_FILE) or {"leads": []}
    leads_changed  = False
    for l in leads_data_mig.get("leads", []):
        if 'value' not in l:
            l['value']    = 0
            leads_changed = True
    if leads_changed:
        write_json(PROMO_LEADS_FILE, leads_data_mig)
        print('[Migrate] Added value field to leads')

    # 13. Living Writer: initialise and migrate to Simplified Creative Ledger model
    lw_data = read_json(LIVING_WRITER_FILE)
    if lw_data is None:
        lw_data = {"stories": []}
        write_json(LIVING_WRITER_FILE, lw_data)
        print('[Migrate] Initialised living_writer.json')
    else:
        changed = False
        for s in lw_data.get("stories", []):
            s.setdefault("id",              str(uuid.uuid4()))
            s.setdefault("title",           "Untitled Story")
            s.setdefault("created_at",      datetime.now().isoformat() + "Z")
            s.setdefault("updated_at",      datetime.now().isoformat() + "Z")
            s.setdefault("current_stage",   1)
            s.setdefault("stage_completion", {"1": False, "2": False, "3": False,
                                              "4": False, "5": False, "6": False, "7": False})
            s.setdefault("draft_complete",    False)
            s.setdefault("draft_complete_at", None)
            s["stage1"] = {"concept_note": s.get("stage1", {}).get("concept_note", ""), "devonthink_path": ""}
            s["stage2"] = {"cts_files": [], "definitions_file": ""}
            s["stage3"] = {"cts_files": [], "definitions_file": ""}
            s["stage4"] = {"cts_files": [], "definitions_file": ""}
            s["stage5"] = {"cts_files": [], "definitions_file": ""}
            s["stage6"] = {"notes": ""}
            s["stage7"] = {"draft_filepath": "", "app": "novelWriter"}
            changed = True
        if changed:
            write_json(LIVING_WRITER_FILE, lw_data)
            print('[Migrate] Migrated living_writer.json to Simplified Creative Ledger model')

    # 14. Data model rename: promo_books.json → works.json (one-time)
    _migrate_books_to_works()

    # 15. Data model rename: chapters.json → modules.json (one-time)
    _migrate_chapters_to_modules()

    # 16. Assets: rename legacy type names (chapter → content, chapter_audio → audio)
    _migrate_asset_types()

    # 17. Promo settings: rename book_serializer → work_serializer
    _migrate_serializer_settings()

    # 18. Content pipeline: add prose, author_note, header_image_path, audio to assets
    pipeline = read_json('content_pipeline.json') or []
    changed  = False
    for entry in pipeline:
        assets = entry.get('assets', {})
        if 'prose' not in assets:
            assets['prose']             = ''
            changed                     = True
        if 'author_note' not in assets:
            assets['author_note']       = ''
            changed                     = True
        if 'header_image_path' not in assets:
            assets['header_image_path'] = None
            changed                     = True
        if 'audio' not in assets:
            assets['audio'] = {
                'local_path':  None,
                's3_url':      None,
                'audio_id':    None,
                'title':       '',
                'duration':    '',
                'min_tier':    1,
                'uploaded_at': None,
            }
            changed = True
        entry['assets'] = assets
    if changed:
        write_json('content_pipeline.json', pipeline)
        print('[Migrate] Added prose/author_note/header_image_path/audio fields to pipeline assets')

    # 19. Settings: add website publishing config
    settings = read_json('settings.json') or {}
    if 'website' not in settings:
        settings['website'] = {
            'website_dir':       '',
            'auto_deploy':       False,
            'lambda_api_url':    'https://jk9fz38v33.execute-api.us-east-1.amazonaws.com',
            'lambda_admin_jwt':  '',
            'lambda_admin_email': '',
        }
        write_json('settings.json', settings)
        print('[Migrate] Added website publishing config to settings')

    # 20. Content pipeline: add workflow stage and status fields (Phase 2 domain model)
    _migrate_workflow_fields()

    # 21. Content pipeline: add sample modules for non-Book work types (Phase 2)
    _migrate_sample_works()


def _migrate_books_to_works():
    """One-time: copy promo_books.json data into works.json with renamed fields."""
    works_path = os.path.join(DATA_DIR, PROMO_WORKS_FILE)
    old_path   = os.path.join(DATA_DIR, 'promo_books.json')

    if not os.path.exists(old_path):
        return  # Already migrated or never existed

    existing_works = read_json(PROMO_WORKS_FILE) or {"works": []}
    if existing_works.get("works"):
        return  # Already populated, don't overwrite

    old_data = read_json('promo_books.json') or {"books": []}
    books    = old_data.get("books", [])
    if not books:
        return

    # Rename book_id field references inside each record
    works = []
    for b in books:
        works.append(b)  # structure is the same; field names in records are IDs not keys

    write_json(PROMO_WORKS_FILE, {"works": works})
    print(f'[Migrate] Migrated {len(works)} books → works.json')


def _migrate_chapters_to_modules():
    """One-time: copy chapters.json data into modules.json with renamed fields."""
    old_path = os.path.join(DATA_DIR, 'chapters.json')

    if not os.path.exists(old_path):
        return

    existing = read_json(PROMO_MODULES_FILE) or {"modules": []}
    if existing.get("modules"):
        return  # Already populated

    old_data = read_json('chapters.json') or {"chapters": []}
    chapters = old_data.get("chapters", [])
    if not chapters:
        return

    # Rename book_id → work_id, keep everything else
    modules = []
    for ch in chapters:
        mod = dict(ch)
        if "book_id" in mod and "work_id" not in mod:
            mod["work_id"] = mod.pop("book_id")
        modules.append(mod)

    write_json(PROMO_MODULES_FILE, {"modules": modules})
    print(f'[Migrate] Migrated {len(modules)} chapters → modules.json')


def _migrate_asset_types():
    """Rename legacy asset type names: chapter→content, chapter_audio→audio."""
    assets_data = read_json(PROMO_ASSETS_FILE) or {"assets": []}
    changed     = False
    for a in assets_data.get("assets", []):
        if a.get("type") == "chapter":
            a["type"] = "content"
            changed   = True
        elif a.get("type") == "chapter_audio":
            a["type"] = "audio"
            changed   = True
        # Also rename book_id → work_id, chapter_id → module_id
        if "book_id" in a and "work_id" not in a:
            a["work_id"] = a.pop("book_id")
            changed = True
        if "chapter_id" in a and "module_id" not in a:
            a["module_id"] = a.pop("chapter_id")
            changed = True
    if changed:
        write_json(PROMO_ASSETS_FILE, assets_data)
        print('[Migrate] Renamed legacy asset types and field names')


def _migrate_serializer_settings():
    """Rename book_serializer → work_serializer in promo_settings.json."""
    settings = read_json(PROMO_SETTINGS_FILE) or {}
    providers = settings.get("ai_providers", {})
    if "book_serializer" in providers and "work_serializer" not in providers:
        providers["work_serializer"] = providers.pop("book_serializer")
        write_json(PROMO_SETTINGS_FILE, settings)
        print('[Migrate] Renamed book_serializer → work_serializer in settings')


def migrate_all_assets_to_taxonomy():
    """Applies role + quantity taxonomy to all existing assets."""
    from services.asset_manager import list_assets, create_asset
    print("[Migration] Patching all assets with new taxonomy...")
    assets = list_assets()
    count  = 0
    for a in assets:
        if "role" not in a or "quantity" not in a:
            create_asset(a)
            count += 1
    print(f"[Migration] Completed. Patched {count} assets.")


def sync_existing_data_to_assets():
    """Consolidates modules (content) and assets (artifacts) from all sources."""
    from services.asset_manager import create_asset, save_module
    print("[AssetSync] Starting hierarchical synchronization v3...")

    # 1. Sync Works (serializer segments)
    works_data = read_json(PROMO_WORKS_FILE) or {"works": []}
    for work in works_data.get("works", []):
        work_id = work['id']
        for chunk in work.get("chunks", []):
            chunk_id = chunk['id']
            save_module({
                "id":       chunk_id,
                "work_id":  work_id,
                "title":    f"Segment: {chunk['content'][:30]}...",
                "prose":    chunk['content'],
                "status":   "final" if chunk.get("status") == "sent" else "draft",
                "ordinal":  chunk.get("part", 1)
            })
            create_asset({
                "id":         f"asset_mod_{chunk_id}",
                "type":       "content",
                "title":      f"Content: {chunk['content'][:20]}",
                "work_id":    work_id,
                "module_id":  chunk_id,
                "production": "done",
                "publishing": "published" if chunk.get("status") == "sent" else "not_published",
                "promotion":  "sent" if chunk.get("status") == "sent" else "not_promoted"
            })

    # 2. Sync Living Writer Stories
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    for story in lw_data.get("stories", []):
        story_id = story['id']
        save_module({
            "id":      f"story_{story_id}",
            "work_id": story_id,
            "title":   story.get('title', 'Unknown Story'),
            "prose":   story.get('synopsis', ''),
            "status":  "final" if story.get("completed") else "draft"
        })
        create_asset({
            "id":         f"asset_story_{story_id}",
            "type":       "content",
            "title":      story.get('title', 'Unknown Story'),
            "work_id":    story_id,
            "module_id":  f"story_{story_id}",
            "production": "in_progress" if not story.get("completed") else "done"
        })

    # 3. Sync Content Pipeline
    cp_data = read_json(CONTENT_PIPELINE_FILE) or []
    for entry in cp_data:
        work_id   = entry.get("book", "Unknown")
        module_id = entry.get("id") or str(uuid.uuid4())

        save_module({
            "id":      module_id,
            "work_id": work_id,
            "title":   entry.get("chapter", "Untitled"),
            "prose":   entry.get("content", ""),
            "status":  "final"
        })
        create_asset({
            "id":         f"cp_{module_id}",
            "type":       "content",
            "title":      entry.get("chapter", "Untitled"),
            "work_id":    work_id,
            "module_id":  module_id,
            "production": "done"
        })

        assets_map = entry.get("assets", {})
        for asset_type in ["tagline", "blurb", "synopsis", "image_prompt"]:
            if assets_map.get(asset_type):
                create_asset({
                    "id":         f"asset_{asset_type}_{module_id}",
                    "type":       asset_type if asset_type != "image_prompt" else "header_image",
                    "title":      f"{asset_type.capitalize()} for {entry.get('chapter')}",
                    "work_id":    work_id,
                    "module_id":  module_id,
                    "production": "done"
                })

    print("[AssetSync] Synchronization complete.")
    migrate_all_assets_to_taxonomy()


def _migrate_workflow_fields():
    """
    Phase 2: Add workflow_stage, work_type, producing_status,
    publishing_status (nested), and promoting_status to every pipeline entry.
    Also nests the legacy per-platform flat fields inside publishing_status.
    """
    pipeline = read_json('content_pipeline.json') or []
    changed  = False

    for entry in pipeline:
        # work_type — all existing entries are Book chapters
        if 'work_type' not in entry:
            entry['work_type'] = 'Book'
            changed = True

        # workflow_stage — infer from platform statuses
        if 'workflow_stage' not in entry:
            platforms = (
                entry.get('vip_group_status', 'not_started'),
                entry.get('patreon_status',   'not_started'),
                entry.get('website_status',   'not_started'),
                entry.get('wa_channel_status','not_started'),
            )
            if any(s in ('in_progress', 'published', 'done') for s in platforms):
                entry['workflow_stage'] = 'publishing'
            else:
                entry['workflow_stage'] = 'producing'
            changed = True

        # producing_status — derived from existing assets
        if 'producing_status' not in entry:
            assets  = entry.get('assets', {})
            prose   = assets.get('prose', '')
            entry['producing_status'] = {
                'essential_asset': 'done' if prose else 'missing',
                'supporting_assets': {
                    'blurb':        'done' if assets.get('blurb')         else 'missing',
                    'tagline':      'done' if assets.get('tagline')       else 'missing',
                    'image_prompt': 'done' if assets.get('image_prompt')  else 'missing',
                    'header_image': 'done' if assets.get('header_image_path') else 'missing',
                    'audio':        'done' if (assets.get('audio') or {}).get('s3_url') else 'missing',
                }
            }
            changed = True

        # publishing_status — nest the flat platform fields
        if 'publishing_status' not in entry:
            entry['publishing_status'] = {
                'vip_group':  entry.get('vip_group_status',  'not_started'),
                'patreon':    entry.get('patreon_status',    'not_started'),
                'website':    entry.get('website_status',    'not_started'),
                'wa_channel': entry.get('wa_channel_status', 'not_started'),
            }
            changed = True

        # promoting_status — default all to not_sent
        if 'promoting_status' not in entry:
            entry['promoting_status'] = {
                'wa_broadcast':   'not_sent',
                'email_excerpt':  'not_sent',
                'serializer_post':'not_sent',
            }
            changed = True

    if changed:
        write_json('content_pipeline.json', pipeline)
        print('[Migrate] Added workflow fields (work_type, workflow_stage, *_status) to pipeline entries')


def _migrate_sample_works():
    """
    Phase 2: Add one sample module each for Podcast, Fundraising Campaign,
    and Retreat (Event) if they don't already exist.
    """
    pipeline   = read_json('content_pipeline.json') or []
    work_types = {e.get('work_type') for e in pipeline}

    samples = []

    if 'Podcast' not in work_types:
        samples.append({
            'id':             'podcast-ep1',
            'work_type':      'Podcast',
            'book':           'INDABA_PODCAST',
            'chapter':        'Pilot Episode',
            'chapter_number': 1,
            'vip_group_status':  'not_started',
            'patreon_status':    'not_started',
            'website_status':    'not_started',
            'wa_channel_status': 'not_started',
            'workflow_stage':    'producing',
            'producing_status': {
                'essential_asset': 'missing',
                'supporting_assets': {
                    'title':       'done',
                    'show_notes':  'missing',
                    'transcript':  'missing',
                    'audiogram':   'missing',
                    'cover_art':   'missing',
                }
            },
            'publishing_status': {
                'spotify':        'not_started',
                'apple_podcasts': 'not_started',
                'website':        'not_started',
            },
            'promoting_status': {
                'wa_broadcast':    'not_sent',
                'email_excerpt':   'not_sent',
                'serializer_post': 'not_sent',
            },
            'assets': {
                'synopsis':           'The debut episode of the Indaba Podcast: Fidel Namisi on the origins of his African fantasy worlds, the discipline of writing across platforms, and what it means to publish on your own terms.',
                'blurb':              'A writer walks you inside his creative process — from blank page to published chapter.',
                'tagline':            'Where African stories are made.',
                'image_prompt':       '',
                'prose':              '',
                'author_note':        '',
                'header_image_path':  None,
                'audio': {
                    'local_path':  None,
                    's3_url':      None,
                    'audio_id':    None,
                    'title':       'Pilot Episode',
                    'duration':    '',
                    'min_tier':    0,
                    'uploaded_at': None,
                }
            },
            'notes':              '',
            'revision':           0,
            'vip_group_revision': 0,
            'patreon_revision':   0,
            'website_revision':   0,
            'wa_channel_revision':0,
        })

    if 'Fundraising Campaign' not in work_types:
        samples.append({
            'id':             'campaign-launch-awareness',
            'work_type':      'Fundraising Campaign',
            'book':           'BOOK_LAUNCH_2026',
            'chapter':        'Awareness Phase',
            'chapter_number': 1,
            'vip_group_status':  'not_started',
            'patreon_status':    'not_started',
            'website_status':    'not_started',
            'wa_channel_status': 'not_started',
            'workflow_stage':    'producing',
            'producing_status': {
                'essential_asset': 'missing',
                'supporting_assets': {
                    'images':       'missing',
                    'progress':     'missing',
                    'testimonials': 'missing',
                    'headline':     'missing',
                    'cta_snippets': 'missing',
                }
            },
            'publishing_status': {
                'gofundme': 'not_started',
                'website':  'not_started',
                'social':   'not_started',
            },
            'promoting_status': {
                'wa_broadcast':    'not_sent',
                'email_excerpt':   'not_sent',
                'serializer_post': 'not_sent',
            },
            'assets': {
                'synopsis':           'Phase 1 of the 2026 book launch campaign. Goal: build awareness among the existing readership and warm audience before opening donations.',
                'blurb':              'Help bring the next chapter of African fantasy to life. Support the book launch and be part of the story.',
                'tagline':            'Be part of the story.',
                'image_prompt':       '',
                'prose':              '',
                'author_note':        '',
                'header_image_path':  None,
                'audio': {
                    'local_path':  None,
                    's3_url':      None,
                    'audio_id':    None,
                    'title':       '',
                    'duration':    '',
                    'min_tier':    0,
                    'uploaded_at': None,
                }
            },
            'notes':              '',
            'revision':           0,
            'vip_group_revision': 0,
            'patreon_revision':   0,
            'website_revision':   0,
            'wa_channel_revision':0,
        })

    if 'Retreat (Event)' not in work_types:
        samples.append({
            'id':             'retreat-2026-invitation',
            'work_type':      'Retreat (Event)',
            'book':           'WRITERS_RETREAT_2026',
            'chapter':        'Invitation',
            'chapter_number': 1,
            'vip_group_status':  'not_started',
            'patreon_status':    'not_started',
            'website_status':    'not_started',
            'wa_channel_status': 'not_started',
            'workflow_stage':    'producing',
            'producing_status': {
                'essential_asset': 'missing',
                'supporting_assets': {
                    'images':          'missing',
                    'schedule':        'missing',
                    'speaker_bios':    'missing',
                    'testimonials':    'missing',
                    'pricing_tiles':   'missing',
                    'cta_snippets':    'missing',
                }
            },
            'publishing_status': {
                'website':      'not_started',
                'landing_page': 'not_started',
                'eventbrite':   'not_started',
            },
            'promoting_status': {
                'wa_broadcast':    'not_sent',
                'email_excerpt':   'not_sent',
                'serializer_post': 'not_sent',
            },
            'assets': {
                'synopsis':           'A curated writers retreat for serious fiction writers. Three days of craft, community, and creative momentum in a distraction-free setting.',
                'blurb':              'Three days. Serious writers. One story at a time.',
                'tagline':            'Write the next chapter of your life.',
                'image_prompt':       '',
                'prose':              '',
                'author_note':        '',
                'header_image_path':  None,
                'audio': {
                    'local_path':  None,
                    's3_url':      None,
                    'audio_id':    None,
                    'title':       '',
                    'duration':    '',
                    'min_tier':    0,
                    'uploaded_at': None,
                }
            },
            'notes':              '',
            'revision':           0,
            'vip_group_revision': 0,
            'patreon_revision':   0,
            'website_revision':   0,
            'wa_channel_revision':0,
        })

    if samples:
        pipeline.extend(samples)
        write_json('content_pipeline.json', pipeline)
        print(f'[Migrate] Added {len(samples)} sample module(s) for new work types')


def retry_failed_messages():
    """Resets failed messages to queued status on startup to allow auto-retry."""
    try:
        m_data  = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
        changed = False
        for m in m_data["messages"]:
            if m.get("status") == "failed":
                m["status"]     = "queued"
                m["updated_at"] = datetime.utcnow().isoformat() + "Z"
                changed = True
        if changed:
            write_json(PROMO_MESSAGES_FILE, m_data)
            print("[Outbox] Reset failed messages for retry.")
    except Exception as e:
        print(f"[Outbox Retry Warning] {e}")
