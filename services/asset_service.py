# Indaba Asset Registry (Single Source of Truth)

ASSET_TYPES = {
    # ESSENTIAL (pipeline-critical)
    "content":      {"quantity": "single",   "role": "essential"},
    "synopsis":     {"quantity": "single",   "role": "essential"},
    "audio":        {"quantity": "single",   "role": "essential"},

    # PROMOTIONAL (enhancement layer)
    "tagline":             {"quantity": "single",   "role": "promotional"},
    "blurb":               {"quantity": "single",   "role": "promotional"},
    "header_image_prompt": {"quantity": "single",   "role": "promotional"},
    "header_image":        {"quantity": "single",   "role": "promotional"},
    "podcast_episode":     {"quantity": "single",   "role": "promotional"},

    # MULTI-ASSETS (promotional)
    "excerpt":     {"quantity": "multiple", "role": "promotional"},
    "image":       {"quantity": "multiple", "role": "promotional"}
}

ROLE_WEIGHT = {
    "essential": 100,
    "promotional": 40
}

def get_asset_config(asset_type):
    """Retrieve the configuration for a given asset type (falling back to default)."""
    return ASSET_TYPES.get(asset_type, {"quantity": "single", "role": "promotional"})

def is_essential(asset_type):
    """Check if an asset type is essential to the core pipeline."""
    return get_asset_config(asset_type).get("role") == "essential"

def is_multiple(asset_type):
    """Check if an asset type supports multiple instances per module."""
    return get_asset_config(asset_type).get("quantity") == "multiple"
