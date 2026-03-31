"""
Action Generator for Indaba.
Deterministic logic to identify gaps in content production.
"""
from services.asset_service import ASSET_TYPES, get_asset_config
from .dependency_engine import is_blocked_state

def generate_actions(all_assets, work_info, modules):
    """
    Scans every module of a work and identifies the highest-priority
    action required for each asset type defined in ASSET_TYPES.
    """
    actions = []

    for work in work_info:
        w_id    = work['id']
        w_title = work.get('title', w_id)

        work_modules = [
            m for m in modules
            if m.get("work_id") == w_id or m.get("book_id") == w_id
        ]

        for mod in work_modules:
            m_id      = mod['id']
            mod_assets = [
                a for a in all_assets
                if a.get("module_id") == m_id or a.get("chapter_id") == m_id
            ]

            for a_type, config in ASSET_TYPES.items():
                matching = [a for a in mod_assets if a['type'] == a_type]
                quantity = config.get("quantity", "single")
                role     = config.get("role", "promotional")

                blocked, blocker = is_blocked_state(a_type, m_id, all_assets)

                if quantity == "single":
                    asset = matching[0] if matching else None
                    if not asset:
                        actions.append({
                            "type":       "create",
                            "asset_type": a_type,
                            "work_id":    w_id,
                            "work_title": w_title,
                            "module_id":  m_id,
                            "label":      f"Create {a_type.replace('_', ' ')}",
                            "blocked":    blocked,
                            "blocker":    blocker,
                            "role":       role
                        })
                    else:
                        status = asset.get("status", {})
                        if status.get("production") != "done":
                            actions.append({
                                "type":       "produce",
                                "asset_id":   asset["id"],
                                "asset_type": a_type,
                                "work_id":    w_id,
                                "work_title": w_title,
                                "module_id":  m_id,
                                "label":      f"Produce {a_type.replace('_', ' ')}",
                                "blocked":    blocked,
                                "blocker":    blocker,
                                "role":       role
                            })
                        elif status.get("publishing") != "published":
                            actions.append({
                                "type":       "publish",
                                "asset_id":   asset["id"],
                                "asset_type": a_type,
                                "work_id":    w_id,
                                "work_title": w_title,
                                "module_id":  m_id,
                                "label":      f"Publish {a_type.replace('_', ' ')}",
                                "blocked":    blocked,
                                "blocker":    blocker,
                                "role":       role
                            })
                        elif status.get("promotion") != "sent":
                            actions.append({
                                "type":       "promote",
                                "asset_id":   asset["id"],
                                "asset_type": a_type,
                                "work_id":    w_id,
                                "work_title": w_title,
                                "module_id":  m_id,
                                "label":      f"Promote {a_type.replace('_', ' ')}",
                                "blocked":    blocked,
                                "blocker":    blocker,
                                "role":       role
                            })

                elif quantity == "multiple":
                    if not matching:
                        actions.append({
                            "type":       "create",
                            "asset_type": a_type,
                            "work_id":    w_id,
                            "work_title": w_title,
                            "module_id":  m_id,
                            "label":      f"Create first {a_type}",
                            "blocked":    blocked,
                            "blocker":    blocker,
                            "role":       role
                        })
                    else:
                        actions.append({
                            "type":       "create",
                            "asset_type": a_type,
                            "work_id":    w_id,
                            "work_title": w_title,
                            "module_id":  m_id,
                            "label":      f"Add {a_type}",
                            "blocked":    blocked,
                            "blocker":    blocker,
                            "role":       role,
                            "is_extra":   True
                        })

    return actions
