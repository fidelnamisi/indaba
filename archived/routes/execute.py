"""
Execution engine routes — thin routing layer.
"""
from flask import Blueprint, jsonify
from services.execution_engine import run_once, EXECUTION_LOG_FILE
from services.action_generator import generate_actions
from services.priority_engine import prioritize
from services.job_runner import runner_instance
from services.asset_manager import list_assets, list_modules, read_json
from utils.constants import PROMO_WORKS_FILE

bp = Blueprint('execute', __name__)


@bp.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    """Execution engine dashboard — next actions, blockers, stats, deals summary."""
    from datetime import datetime, timedelta
    from utils.constants import PROMO_LEADS_FILE

    assets_list = list_assets()
    works_data  = read_json(PROMO_WORKS_FILE) or {"works": []}
    modules     = list_modules()

    all_actions = generate_actions(assets_list, works_data.get("works", []), modules)
    prioritized = prioritize(all_actions)

    stats = {"production_pending": 0, "ready_to_publish": 0, "ready_to_promote": 0}
    for a in assets_list:
        p   = a.get("status", {}).get("production")
        pub = a.get("status", {}).get("publishing")
        pro = a.get("status", {}).get("promotion")
        if p != "publish":
            stats["production_pending"] += 1
        elif pub != "published":
            stats["ready_to_publish"] += 1
        elif pro != "sent":
            stats["ready_to_promote"] += 1

    leads_data     = read_json(PROMO_LEADS_FILE) or {"leads": []}
    all_leads      = leads_data.get("leads", [])
    open_deals     = [l for l in all_leads if l.get('stage') not in ['won', 'lost']]
    now_dt         = datetime.utcnow()
    seven_days_ago = (now_dt - timedelta(days=7)).isoformat() + "Z"
    month_start    = now_dt.replace(day=1).isoformat() + "Z"

    follow_up_needed = []
    for l in open_deals:
        log       = l.get('communication_log', [])
        last_comm = max((e.get('timestamp', '') for e in log), default=None) if log else None
        if not last_comm or last_comm < seven_days_ago:
            follow_up_needed.append(l)

    won_this_month  = [l for l in all_leads if l.get('stage') == 'won'  and l.get('updated_at', '') >= month_start]
    lost_this_month = [l for l in all_leads if l.get('stage') == 'lost' and l.get('updated_at', '') >= month_start]

    deals_summary = {
        "open_deals":       len(open_deals),
        "won_this_month":   len(won_this_month),
        "lost_this_month":  len(lost_this_month),
        "follow_up_needed": len(follow_up_needed),
        "follow_up_leads":  [{"id": l['id'], "product": l.get('product', ''),
                               "contact_name": l.get('contact_name', ''),
                               "stage": l.get('stage', '')}
                              for l in follow_up_needed[:5]]
    }

    return jsonify({
        "next_actions":   prioritized[:10],
        "blockers":       [a for a in all_actions if a.get("blocked")],
        "stats":          stats,
        "runner_running": runner_instance.running,
        "deals_summary":  deals_summary,
    })


@bp.route('/api/next-actions', methods=['GET'])
def get_next_actions():
    assets_list = list_assets()
    works_data  = read_json(PROMO_WORKS_FILE) or {"works": []}
    modules     = list_modules()
    all_actions = generate_actions(assets_list, works_data.get("works", []), modules)
    return jsonify(prioritize(all_actions))


@bp.route('/api/blockers', methods=['GET'])
def get_blockers():
    assets_list = list_assets()
    works_data  = read_json(PROMO_WORKS_FILE) or {"works": []}
    modules     = list_modules()
    all_actions = generate_actions(assets_list, works_data.get("works", []), modules)
    return jsonify([a for a in all_actions if a.get("blocked")])


@bp.route('/api/execution-log', methods=['GET'])
def get_execution_log():
    data = read_json(EXECUTION_LOG_FILE) or {"logs": []}
    return jsonify(data["logs"])


@bp.route('/api/run', methods=['POST'])
def manual_run():
    return jsonify(run_once())


@bp.route('/api/runner/status', methods=['GET'])
def get_runner_status():
    return jsonify({"running": runner_instance.running})


@bp.route('/api/runner/start', methods=['POST'])
def start_runner():
    runner_instance.start()
    return jsonify({"running": True})


@bp.route('/api/runner/stop', methods=['POST'])
def stop_runner():
    runner_instance.stop()
    return jsonify({"running": False})
