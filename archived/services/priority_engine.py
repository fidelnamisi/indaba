"""
Priority Engine for Indaba.
Scores and sorts actions based on business impact and feasibility.
"""
from services.asset_service import ASSET_TYPES, ROLE_WEIGHT, get_asset_config

STAGE_WEIGHT = {
    "create": 100,
    "produce": 80,
    "publish": 60,
    "promote": 40
}

BLOCK_PENALTY = -500

def score_action(action):
    """
    Computes a score for a single action using the new Role + Stage taxonomy.
    Score = RoleWeight + StageWeight + BlockPenalty
    """
    a_type = action.get("asset_type")
    stage_type = action.get("type")
    blocked = action.get("blocked", False)
    
    # Get config from registry
    config = get_asset_config(a_type)
    role = config.get("role", "promotional")
    role_w = ROLE_WEIGHT.get(role, 40)
    
    score = role_w + STAGE_WEIGHT.get(stage_type, 10)
    
    if blocked:
        score += BLOCK_PENALTY
        
    return score

def prioritize(actions):
    """
    Sorts actions by descending score.
    Returns a list of the top 10 prioritized actions.
    """
    for action in actions:
        action["score"] = score_action(action)
        
    # Sort: Descending score, then Alphabetical Book Title to ensure stability
    sorted_actions = sorted(
        actions, 
        key=lambda x: (-x["score"], x.get("book_title", ""), x.get("chapter_id", ""))
    )
    
    return sorted_actions
