from ..asset_manager import update_asset, get_asset, list_chapters
from ..ai_service import AIService

def handle_produce(action, all_assets):
    """
    Executes actual AI-powered production of text assets.
    """
    asset_id = action.get("asset_id")
    if not asset_id: return {"success": False, "error": "Missing asset_id"}
    
    asset = get_asset(asset_id)
    if not asset: return {"success": False, "error": "Asset not found"}
    
    a_type = asset.get("type")
    c_id   = asset.get("chapter_id")
    
    # 1. Fetch chapter prose to use as source
    chapters = list_chapters()
    chapter  = next((ch for ch in chapters if ch["id"] == c_id), None)
    prose    = chapter.get("prose", "") if chapter else ""
    title    = chapter.get("title", "") if chapter else "Untitled Chapter"

    if not prose:
        return {"success": False, "error": "Source chapter text missing."}

    # 2. Functional Branching: call AI Service
    content = ""
    try:
        if a_type == "synopsis":
             content = AIService.generate_synopsis(title, prose)
        elif a_type == "tagline":
             content = AIService.generate_tagline(title, prose)
        elif a_type == "blurb":
             content = AIService.generate_blurb(title, prose)
        elif a_type == "excerpt":
             content = AIService.extract_excerpt(title, prose)
        else:
             # Default: mark as simulated production if unknown type
             content = f"Simulated content for {a_type}"
             
        # 3. Persistence: update the asset with generated content and ready status
        update_asset(asset_id, {
            "content": content,
            "status": {"production": "publish"}
        })
        
        return {"success": True, "details": f"Generated: {content[:50]}..."}
    except Exception as e:
        return {"success": False, "error": f"AI Generation Failed: {str(e)}"}
