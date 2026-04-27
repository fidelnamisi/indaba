"""
Asset routes — thin routing layer.
"""
from flask import Blueprint, jsonify, request
from services.asset_manager import (
    create_asset, update_asset, delete_asset,
    list_assets, get_asset,
    save_module, update_module, delete_module, list_modules
)
from services.asset_service import ASSET_TYPES

bp = Blueprint('assets', __name__)


@bp.route('/api/assets', methods=['POST'])
def add_asset_manual():
    data = request.get_json()
    return jsonify(create_asset(data))


@bp.route('/api/assets/<asset_id>', methods=['PUT'])
def edit_asset_manual(asset_id):
    data = request.get_json()
    res  = update_asset(asset_id, data)
    if res:
        return jsonify(res)
    return jsonify({"error": "Asset not found"}), 404


@bp.route('/api/assets/<asset_id>', methods=['DELETE'])
def remove_asset_manual(asset_id):
    if delete_asset(asset_id):
        return jsonify({"success": True})
    return jsonify({"error": "Asset not found"}), 404


@bp.route('/api/assets/<asset_id>/run-pipeline', methods=['POST'])
def handle_asset_pipeline(asset_id):
    asset = get_asset(asset_id)
    if not asset:
        return jsonify({"error": "Asset not found"}), 404
    stages       = ["not_started", "record", "edit", "master", "publish"]
    current_prod = asset["status"]["production"]
    try:
        idx = stages.index(current_prod)
        if idx < len(stages) - 1:
            next_stage = stages[idx + 1]
            updates    = {"status": {"production": next_stage}}
            if next_stage == "publish":
                updates["status"]["publishing"] = "published"
            return jsonify(update_asset(asset_id, updates))
    except ValueError:
        pass
    return jsonify(asset)


@bp.route('/api/modules', methods=['POST'])
def create_module():
    import uuid
    from datetime import datetime
    data = request.get_json()
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    module = {
        "id":         str(uuid.uuid4()),
        "title":      title,
        "prose":      data.get('prose', '').strip(),
        "status":     data.get('status', 'draft'),
        "work_id":    data.get('work_id', ''),
        "ordinal":    data.get('ordinal', 0),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    save_module(module)
    return jsonify(module), 201


@bp.route('/api/modules/<module_id>', methods=['GET'])
def get_module(module_id):
    """Return full module data including prose for the edit modal."""
    modules = list_modules()
    module  = next((m for m in modules if m['id'] == module_id), None)
    if not module:
        return jsonify({"error": "Module not found"}), 404
    module_assets = [a for a in list_assets() if a.get('module_id') == module_id or a.get('chapter_id') == module_id]
    return jsonify({**module, "assets": module_assets})


@bp.route('/api/modules/<module_id>', methods=['PUT'])
def edit_module(module_id):
    data = request.get_json()
    res  = update_module(module_id, data)
    if res:
        return jsonify(res)
    return jsonify({"error": "Module not found"}), 404


@bp.route('/api/modules/<module_id>', methods=['DELETE'])
def remove_module(module_id):
    if delete_module(module_id):
        return jsonify({"success": True})
    return jsonify({"error": "Module not found"}), 404


# Backwards-compat aliases
@bp.route('/api/chapters/<module_id>', methods=['GET'])
def get_module_compat(module_id):
    return get_module(module_id)

@bp.route('/api/chapters/<module_id>', methods=['PUT'])
def edit_module_compat(module_id):
    return edit_module(module_id)

@bp.route('/api/chapters/<module_id>', methods=['DELETE'])
def remove_module_compat(module_id):
    return remove_module(module_id)


@bp.route('/api/modules/<module_id>/generate-asset', methods=['POST'])
def generate_module_asset(module_id):
    """Generate asset content via AI using the module's prose and a saved prompt."""
    from services.ai_service import call_ai
    from utils.json_store import read_json
    from utils.constants import PROMO_SETTINGS_FILE

    data             = request.get_json() or {}
    asset_type       = data.get('asset_type', '')
    prompt_version   = data.get('prompt_version', 'A')
    reference_image  = data.get('reference_image_url', '').strip()
    custom_prompt    = data.get('custom_prompt', '').strip()

    modules = list_modules()
    module  = next((m for m in modules if m['id'] == module_id), None)
    if not module:
        # Fallback: look in content_pipeline.json (new domain model entries)
        pipeline = read_json('content_pipeline.json') or []
        entry    = next((e for e in pipeline if e['id'] == module_id), None)
        if entry:
            module = {
                'id':    module_id,
                'title': entry.get('chapter', ''),
                'prose': (entry.get('assets') or {}).get('prose', ''),
            }
        else:
            return jsonify({"error": "Module not found"}), 404

    # Always pull the full pipeline entry so we have access to all assets
    _pipeline      = read_json('content_pipeline.json') or []
    _pipeline_entry = next((e for e in _pipeline if e['id'] == module_id), None)
    _entry_assets   = (_pipeline_entry.get('assets') or {}) if _pipeline_entry else {}

    prose = module.get('prose', '').strip() or _entry_assets.get('prose', '').strip()
    if not prose:
        return jsonify({"error": "This module has no prose. Add prose via Edit Module first."}), 400

    # Synopsis-derived assets (tagline, blurb, image prompt) use the synopsis as input
    # when it exists — synopsis is more focused and produces better results than raw prose.
    SYNOPSIS_DERIVED = {'tagline', 'blurb', 'header_image_prompt'}
    synopsis_text = _entry_assets.get('synopsis', '').strip()
    if not synopsis_text:
        synopsis_text = (module.get('assets') or {}).get('synopsis', '').strip()
    input_text = synopsis_text if (asset_type in SYNOPSIS_DERIVED and synopsis_text) else prose

    # Resolve prompt text
    if custom_prompt:
        prompt_text = custom_prompt
    else:
        settings      = read_json(PROMO_SETTINGS_FILE) or {}
        asset_prompts = settings.get('asset_prompts', [])
        cfg           = next((p for p in asset_prompts if p.get('asset_type') == asset_type), None)
        if not cfg:
            return jsonify({"error": f"No prompt configured for '{asset_type}'. Add one in Settings → Asset Generation Prompts."}), 400
        ver_data    = cfg.get('versions', {}).get(prompt_version, {})
        prompt_text = ver_data.get('prompt', '')
        if not prompt_text:
            return jsonify({"error": f"Prompt version {prompt_version} is empty. Edit it in Settings."}), 400

    # Inject input text (synopsis for derived types, prose otherwise).
    # Replace {{prose}} placeholder, or append if absent.
    if '{{prose}}' in prompt_text:
        full_prompt = prompt_text.replace('{{prose}}', input_text)
    else:
        input_label = 'SYNOPSIS' if (asset_type in SYNOPSIS_DERIVED and synopsis_text) else 'CHAPTER TEXT'
        full_prompt = f"{prompt_text}\n\n---\n{input_label}:\n{input_text}"

    # Optional: vision analysis of reference image (two-step)
    image_description = ''
    if reference_image:
        try:
            vision_messages = [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": reference_image}},
                {"type": "text", "text": "Describe this image in detail, focusing on: visual composition, lighting, mood, color palette, subject matter, setting, and atmosphere. Be specific and visual."}
            ]}]
            image_description = call_ai('asset_generator', vision_messages, max_tokens=400)
            full_prompt += f"\n\nVisual reference analysis (incorporate style and mood into your output):\n{image_description}"
        except Exception:
            pass  # Vision not supported by provider — skip silently

    # Parse max word count from the prompt so we can set a hard token ceiling.
    # Looks for patterns like "100-150 words", "max 200 words", "150 words maximum".
    import re as _re
    _wc_match = _re.search(
        r'(?:max(?:imum)?|up to|under|no more than)?\s*(\d+)\s*(?:[-–]\s*\d+\s*)?words?(?:\s*(?:max(?:imum)?|maximum|limit))?',
        full_prompt, _re.IGNORECASE
    )
    # Also catch the upper bound of a range like "100–150 words"
    _range_match = _re.search(r'(\d+)\s*[-–]\s*(\d+)\s*words?', full_prompt, _re.IGNORECASE)
    if _range_match:
        max_word_limit = int(_range_match.group(2))
    elif _wc_match:
        max_word_limit = int(_wc_match.group(1))
    else:
        max_word_limit = 400  # safe default

    # tokens ≈ words × 1.4; add 20% headroom then cap at 1200
    max_tokens_for_call = min(int(max_word_limit * 1.4 * 1.2), 1200)

    system_message = (
        "You are a professional writing assistant. "
        f"CRITICAL RULE: Your output MUST NOT exceed {max_word_limit} words. "
        "Count your words mentally before responding. If you are approaching the limit, conclude your thought and stop. "
        "Return ONLY the requested content — no preamble, no labels, no commentary."
    )

    try:
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user",   "content": full_prompt},
        ]
        result = call_ai('asset_generator', messages, max_tokens=max_tokens_for_call)
        return jsonify({"content": result, "asset_type": asset_type, "image_description": image_description})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/api/modules/<module_id>/generate-header-image', methods=['POST'])
def generate_module_header_image(module_id):
    """Generate a chapter header image via Google Imagen 3, using the module's image_prompt asset."""
    import os, base64, requests as _req
    from utils.json_store import read_json, write_json, BASE_DIR

    # Load pipeline entry
    pipeline = read_json('content_pipeline.json') or []
    entry = next((e for e in pipeline if e['id'] == module_id), None)
    if not entry:
        return jsonify({"error": "Module not found"}), 404

    assets = entry.get('assets') or {}
    image_prompt = assets.get('image_prompt', '').strip()
    if not image_prompt:
        return jsonify({"error": "No Image Prompt found for this module. Generate the Image Prompt first."}), 400

    sa_path = os.environ.get('GOOGLE_SA_KEY', '')
    if not sa_path or not os.path.exists(sa_path):
        return jsonify({"error": "GOOGLE_SA_KEY not set or file not found."}), 503

    try:
        from capabilities.create.generator import _get_vertex_token

        token = _get_vertex_token(sa_path)

        # Use the image prompt as-is — do not append demographic/style suffixes
        # that could contradict the prompt content and trigger safety filters.
        full_prompt = image_prompt + ", no text overlay, cinematic composition"

        img_resp = _req.post(
            "https://us-central1-aiplatform.googleapis.com/v1/projects/"
            "gen-lang-client-0717388888/locations/us-central1/publishers/google/"
            "models/imagen-3.0-generate-001:predict",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"instances": [{"prompt": full_prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "16:9", "personGeneration": "allow_all"}},
            timeout=90,
        )
        if img_resp.status_code == 429:
            return jsonify({"error": "Imagen rate limit hit — wait a few seconds and try again."}), 429
        if img_resp.status_code != 200:
            return jsonify({"error": f"Imagen API error {img_resp.status_code}: {img_resp.text[:200]}"}), 502

        resp_json = img_resp.json()
        predictions = resp_json.get("predictions") or []
        if not predictions:
            return jsonify({
                "error": "Imagen returned no image (safety filter). "
                         "Try rephrasing your Image Prompt — avoid depicting children, "
                         "violence, or specific ethnicities combined with age descriptors."
            }), 422

        img_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])

        images_dir = os.path.join(BASE_DIR, 'data', 'generated_images')
        os.makedirs(images_dir, exist_ok=True)
        filename = f"header_{module_id}.jpg"
        img_path = os.path.join(images_dir, filename)
        tmp_path = img_path + '.tmp'
        with open(tmp_path, 'wb') as f:
            f.write(img_bytes)
        os.replace(tmp_path, img_path)

        # Update the pipeline entry
        assets['header_image_path'] = f"/data/images/{filename}"
        entry['assets'] = assets
        # Also mark header_image as done in supporting_assets
        ps = entry.setdefault('producing_status', {})
        sa = ps.setdefault('supporting_assets', {})
        sa['header_image'] = 'done'
        write_json('content_pipeline.json', pipeline)

        return jsonify({"ok": True, "image_url": f"/data/images/{filename}"})

    except Exception as e:
        return jsonify({"error": f"Image generation failed: {e}"}), 500


@bp.route('/api/command-center', methods=['GET'])
def get_command_center():
    """Hierarchical map of Works → Modules → Role-Grouped Assets."""
    from utils.json_store import read_json
    from utils.constants import PROMO_WORKS_FILE
    from services.asset_manager import list_modules

    assets_list = list_assets()
    modules     = list_modules()

    works_data   = read_json(PROMO_WORKS_FILE) or {"works": []}
    works_lookup = {w["id"]: w["title"] for w in works_data.get("works", [])}

    # Start with all works from works.json (even those with no modules yet)
    work_ids_from_modules = set(m.get("work_id") or m.get("book_id") for m in modules if m.get("work_id") or m.get("book_id"))
    work_ids_from_works   = set(w["id"] for w in works_data.get("works", []))
    work_ids = sorted(work_ids_from_modules | work_ids_from_works)

    # Also include LW story titles as work names
    from utils.constants import LIVING_WRITER_FILE
    lw_data = read_json(LIVING_WRITER_FILE) or {"stories": []}
    for s in lw_data.get("stories", []):
        if s["id"] not in works_lookup:
            works_lookup[s["id"]] = s.get("title", s["id"])

    # Include content pipeline book names
    from utils.constants import CONTENT_PIPELINE_FILE
    cp_data = read_json(CONTENT_PIPELINE_FILE) or []
    for entry in cp_data:
        book_id = entry.get("book")
        if book_id and book_id not in works_lookup:
            works_lookup[book_id] = book_id

    result = []

    for w_id in work_ids:
        work_modules = [m for m in modules if (m.get("work_id") or m.get("book_id")) == w_id]
        work_entry   = {
            "work_id":    w_id,
            "work_title": works_lookup.get(w_id, w_id),
            "modules":    []
        }
        for mod in work_modules:
            m_id      = mod['id']
            m_assets  = [a for a in assets_list if (a.get("module_id") or a.get("chapter_id")) == m_id]
            essential, promotional = [], []
            for a_type, config in ASSET_TYPES.items():
                matching    = [a for a in m_assets if a['type'] == a_type]
                asset_entry = {
                    "type":     a_type,
                    "role":     config['role'],
                    "quantity": config['quantity'],
                    "exists":   len(matching) > 0,
                    "count":    len(matching),
                    "items": [{
                        "asset_id":   m["id"],
                        "type":       m.get("type", a_type),
                        "role":       m.get("role", config.get("role")),
                        "title":      m.get("title", ""),
                        "content":    m.get("content", ""),
                        "work_id":    m.get("work_id") or m.get("book_id"),
                        "module_id":  m.get("module_id") or m.get("chapter_id"),
                        "production": m["status"]["production"],
                        "publishing": m["status"]["publishing"],
                        "promotion":  m["status"]["promotion"],
                        "created_at": m.get("created_at", ""),
                        "updated_at": m.get("updated_at", ""),
                    } for m in matching]
                }
                if config['role'] == "essential":
                    essential.append(asset_entry)
                else:
                    promotional.append(asset_entry)
            work_entry["modules"].append({
                "module_id":    m_id,
                "module_title": mod.get("title", f"Module: {m_id}"),
                "prose_preview": mod.get("prose", "")[:100] + "...",
                "status":       mod.get("status", "draft"),
                "essential":    essential,
                "promotional":  promotional,
            })
        result.append(work_entry)

    return jsonify(result)
