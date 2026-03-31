"""
Execution Engine for Indaba.
Pulls prioritized recommendations and executes exactly one valid task.
"""
import uuid
from datetime import datetime
from .asset_manager import list_assets, list_chapters, read_json, write_json
from .action_generator import generate_actions
from .priority_engine import prioritize

# Import handlers
from .handlers.create import handle_create
from .handlers.produce import handle_produce
from .handlers.publish import handle_publish
from .handlers.promote import handle_promote

EXECUTION_LOG_FILE = 'execution_log.json'

def log_execution(action, result):
    """Save execution record to log."""
    log_data = read_json(EXECUTION_LOG_FILE) or {"logs": []}
    now = datetime.utcnow().isoformat() + "Z"
    
    new_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": now,
        "action": action,
        "result": result
    }
    log_data["logs"].insert(0, new_entry) # Most recent first
    # Keep last 100 logs
    log_data["logs"] = log_data["logs"][:100]
    write_json(EXECUTION_LOG_FILE, log_data)

def run_once():
    """
    1. Collect Next Actions using hierarchical taxonomy
    2. Pick first unblocked action
    3. Execute with appropriate handler
    4. Log result
    """
    assets = list_assets()
    books_data = read_json('promo_books.json') or {"books": []}
    chapters = list_chapters()
    
    # 1. Generate all possible actions considering multi-assets and role-weighting
    all_actions = generate_actions(assets, books_data.get("books", []), chapters)
    
    # 2. Prioritize based on ROLE_WEIGHT and STAGE_WEIGHT
    prioritized = prioritize(all_actions)
    
    # 3. Filter for first unblocked action
    target_action = None
    for a in prioritized:
        if not a.get("blocked"):
            target_action = a
            break
            
    if not target_action:
        return {"status": "idle", "message": "No unblocked actions available."}
        
    act_type = target_action.get("type")
    handlers = {
        "create":  handle_create,
        "produce": handle_produce,
        "publish": handle_publish,
        "promote": handle_promote
    }
    
    handler = handlers.get(act_type)
    if not handler:
        return {"status": "error", "message": f"Source handler for {act_type} missing."}
        
    # Execution
    try:
        result = handler(target_action, assets)
        log_execution(target_action, result)
        return {"status": "success", "action": target_action, "result": result}
    except Exception as e:
        err_res = {"status": "error", "message": str(e)}
        log_execution(target_action, err_res)
        return err_res
