import uuid
from datetime import datetime
from services.asset_service import get_asset_config

# Re-export json_store so existing imports (e.g. execution_engine) keep working
from utils.json_store import read_json, write_json, DATA_DIR, BASE_DIR

PROMO_ASSETS_FILE   = 'assets.json'
PROMO_WORKS_FILE    = 'works.json'
PROMO_MODULES_FILE  = 'modules.json'
PROMO_MESSAGES_FILE = 'promo_messages.json'

# Backwards-compat aliases
PROMO_BOOKS_FILE    = PROMO_WORKS_FILE
PROMO_CHAPTERS_FILE = PROMO_MODULES_FILE

def list_assets():
    data = read_json(PROMO_ASSETS_FILE) or {"assets": []}
    return data.get("assets", [])

def list_modules():
    data = read_json(PROMO_MODULES_FILE) or {"modules": []}
    return data.get("modules", [])

# Backwards-compat alias
def list_chapters():
    return list_modules()

def get_asset(asset_id):
    assets = list_assets()
    return next((a for a in assets if a["id"] == asset_id), None)

def create_asset(data):
    """Taxonomy-aware asset creation/upsert (preserves existing content on re-sync)."""
    assets_data = read_json(PROMO_ASSETS_FILE) or {"assets": []}
    asset_id = data.get("id") or str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    a_type = data.get("type", "content")
    # Migrate legacy type names
    if a_type == "chapter":
        a_type = "content"
    elif a_type == "chapter_audio":
        a_type = "audio"

    config = get_asset_config(a_type)

    new_asset = {
        "id":               asset_id,
        "type":             a_type,
        "role":             data.get("role") or config.get("role", "promotional"),
        "quantity":         data.get("quantity") or config.get("quantity", "single"),
        "title":            data.get("title", "Untitled"),
        "work_id":          data.get("work_id") or data.get("book_id"),
        "module_id":        data.get("module_id") or data.get("chapter_id"),
        "entity_id":        data.get("entity_id"),
        "source_type":      data.get("source_type", "original"),
        "source_reference": data.get("source_reference"),
        "version":          data.get("version", 1),
        "content":          data.get("content", ""),
        "order":            data.get("order", 0),
        "status": {
            "production": data.get("production", "not_started"),
            "publishing": data.get("publishing", "not_published"),
            "promotion":  data.get("promotion",  "not_promoted")
        },
        "storage": {
            "local_path": data.get("local_path"),
            "cloud_url":  data.get("cloud_url")
        },
        "distribution": data.get("distribution", []),
        "created_at":   now,
        "updated_at":   now
    }

    # Upsert by id — preserve existing content/status if already present
    existing = next((a for a in assets_data["assets"] if a["id"] == asset_id), None)
    if existing:
        if not data.get("content"):
            new_asset["content"] = existing.get("content", "")
        if not any(k in data for k in ("production", "publishing", "promotion")):
            new_asset["status"] = existing.get("status", new_asset["status"])
        new_asset["created_at"] = existing.get("created_at", now)
        # Preserve work_id/module_id if not explicitly provided
        if not new_asset["work_id"]:
            new_asset["work_id"] = existing.get("work_id") or existing.get("book_id")
        if not new_asset["module_id"]:
            new_asset["module_id"] = existing.get("module_id") or existing.get("chapter_id")
        assets_data["assets"] = [a for a in assets_data["assets"] if a["id"] != asset_id]

    assets_data["assets"].append(new_asset)
    write_json(PROMO_ASSETS_FILE, assets_data)
    return new_asset

def update_asset(asset_id, updates):
    assets_data = read_json(PROMO_ASSETS_FILE) or {"assets": []}
    asset = next((a for a in assets_data["assets"] if a["id"] == asset_id), None)
    if not asset: return None

    if "status" in updates:
        for k, v in updates["status"].items():
            if "status" not in asset: asset["status"] = {}
            asset["status"][k] = v

    for k, v in updates.items():
        if k != "status":
            asset[k] = v

    asset["updated_at"] = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_ASSETS_FILE, assets_data)
    return asset

def create_promo_message(data):
    """Pushes a message record into the universal Outbox (promo_messages.json)."""
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now = datetime.utcnow().isoformat() + "Z"

    msg_id = str(uuid.uuid4())
    new_msg = {
        "id":               msg_id,
        "recipient_phone":  data.get("recipient_phone"),
        "recipient_name":   data.get("recipient_name", "Contact"),
        "content":          data.get("content"),
        "media_url":        data.get("media_url"),
        "status":           "queued",
        "source":           data.get("source", "asset_registry"),
        "source_ref":       data.get("source_ref", {}),
        "scheduled_at":     data.get("scheduled_at"),
        "created_at":       now,
        "updated_at":       now
    }
    msgs_data["messages"].append(new_msg)
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    return new_msg

def delete_asset(asset_id):
    """Removes an asset from the registry."""
    assets_data = read_json(PROMO_ASSETS_FILE) or {"assets": []}
    original_count = len(assets_data["assets"])
    assets_data["assets"] = [a for a in assets_data["assets"] if a["id"] != asset_id]

    if len(assets_data["assets"]) < original_count:
        write_json(PROMO_ASSETS_FILE, assets_data)
        return True
    return False

def save_module(data):
    """Upsert a module record by id."""
    modules_data = read_json(PROMO_MODULES_FILE) or {"modules": []}
    existing = next((m for m in modules_data["modules"] if m["id"] == data["id"]), None)
    if existing:
        existing.update(data)
    else:
        modules_data["modules"].append(data)
    write_json(PROMO_MODULES_FILE, modules_data)
    return data

# Backwards-compat alias
def save_chapter(data):
    return save_module(data)

def update_module(module_id, updates):
    """Updates module metadata (title, prose, status)."""
    data = read_json(PROMO_MODULES_FILE) or {"modules": []}
    module = next((m for m in data["modules"] if m["id"] == module_id), None)
    if not module: return None

    for k, v in updates.items():
        module[k] = v

    write_json(PROMO_MODULES_FILE, data)
    return module

# Backwards-compat alias
def update_chapter(chapter_id, updates):
    return update_module(chapter_id, updates)

def delete_module(module_id):
    """Removes a module and all its associated assets (cascading)."""
    # 1. Delete assets
    assets_data = read_json(PROMO_ASSETS_FILE) or {"assets": []}
    assets_data["assets"] = [
        a for a in assets_data["assets"]
        if a.get("module_id") != module_id and a.get("chapter_id") != module_id
    ]
    write_json(PROMO_ASSETS_FILE, assets_data)

    # 2. Delete module
    modules_data = read_json(PROMO_MODULES_FILE) or {"modules": []}
    original_count = len(modules_data["modules"])
    modules_data["modules"] = [m for m in modules_data["modules"] if m["id"] != module_id]

    if len(modules_data["modules"]) < original_count:
        write_json(PROMO_MODULES_FILE, modules_data)
        return True
    return False

# Backwards-compat alias
def delete_chapter(chapter_id):
    return delete_module(chapter_id)

def delete_work(work_id):
    """Removes a work and all its modules + assets (full cascading)."""
    # 1. Delete assets
    assets_data = read_json(PROMO_ASSETS_FILE) or {"assets": []}
    assets_data["assets"] = [
        a for a in assets_data["assets"]
        if a.get("work_id") != work_id and a.get("book_id") != work_id
    ]
    write_json(PROMO_ASSETS_FILE, assets_data)

    # 2. Delete modules
    modules_data = read_json(PROMO_MODULES_FILE) or {"modules": []}
    modules_data["modules"] = [
        m for m in modules_data["modules"]
        if m.get("work_id") != work_id and m.get("book_id") != work_id
    ]
    write_json(PROMO_MODULES_FILE, modules_data)

    # 3. Delete work record
    works_data = read_json(PROMO_WORKS_FILE) or {"works": []}
    original_count = len(works_data["works"])
    works_data["works"] = [w for w in works_data["works"] if w["id"] != work_id]

    if len(works_data["works"]) < original_count:
        write_json(PROMO_WORKS_FILE, works_data)

    return True

# Backwards-compat alias
def delete_book(book_id):
    return delete_work(book_id)
