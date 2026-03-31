from services.asset_service import is_essential, get_asset_config
from .asset_manager import list_modules

# ── RULES ────────────────────────────────────────────────────────────────────
DEPENDENCY_MAP = {
    "audio":          ["content"],
    "synopsis":       ["content"],
    "tagline":        ["content"],
    "blurb":          ["content"],
    "excerpt":        ["content"],
    "header_image":   ["content"],
    "image":          ["content"],
    "podcast_episode": ["audio"]
}

def is_blocked_state(asset_type, module_id, all_assets):
    """
    Returns (blocked, blocker_type) indicating if the asset cannot proceed.
    """
    # 1. Source Dependency Check (Module status)
    # If the module is still in 'draft' status, ALL promotional assets are blocked.
    modules = list_modules()
    module  = next((m for m in modules if m["id"] == module_id), None)

    if module and module.get("status") == "draft":
        if asset_type != "content":
            return True, "module_is_draft"

    # 2. Asset Type Dependencies
    deps = DEPENDENCY_MAP.get(asset_type, [])
    if not deps:
        return False, None

    # Support both old (chapter_id) and new (module_id) field names during migration
    module_assets = [
        a for a in all_assets
        if a.get("module_id") == module_id or a.get("chapter_id") == module_id
    ]

    for dep_type in deps:
        dep_asset = next((a for a in module_assets if a["type"] == dep_type), None)

        if is_essential(dep_type):
            if not dep_asset:
                return True, f"missing_{dep_type}"
            prod = dep_asset.get("status", {}).get("production")
            if prod not in ("done", "publish"):
                return True, f"unfinished_{dep_type}"

    return False, None
