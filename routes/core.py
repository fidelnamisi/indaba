"""
Core routes — hub summary, settings, plugins, frontend serving.
"""
from flask import Blueprint, jsonify, request, render_template, redirect, url_for
from utils.json_store import read_json, write_json
from utils.constants import (
    PROMO_CONTACTS_FILE, PROMO_LEADS_FILE, PROMO_MESSAGES_FILE,
    _DEFAULTS
)
from utils.helpers import get_constants

bp = Blueprint('core', __name__)


# ── Hub summary ───────────────────────────────────────────────────────────────

@bp.route('/api/hub/summary')
def api_hub_summary():
    pipeline           = read_json('content_pipeline.json') or []
    modules_producing  = sum(1 for e in pipeline if e.get('workflow_stage') == 'producing')
    modules_publishing = sum(1 for e in pipeline if e.get('workflow_stage') == 'publishing')
    modules_promoting  = sum(1 for e in pipeline if e.get('workflow_stage') == 'promoting')

    contacts_data = read_json(PROMO_CONTACTS_FILE) or {"contacts": []}
    leads_data    = read_json(PROMO_LEADS_FILE) or {"leads": []}
    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}

    open_leads      = [l for l in leads_data.get("leads", []) if l.get('stage') not in ['won', 'lost']]
    queued_messages = [m for m in messages_data.get("messages", []) if m.get('status') == 'queued']

    return jsonify({
        'pipeline': {
            'producing':  modules_producing,
            'publishing': modules_publishing,
            'promoting':  modules_promoting,
        },
        'promote': {
            'contacts_count':  len(contacts_data.get("contacts", [])),
            'open_leads':      len(open_leads),
            'messages_queued': len(queued_messages),
        }
    })


# ── Settings ──────────────────────────────────────────────────────────────────

@bp.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(read_json('settings.json') or {})


@bp.route('/api/settings', methods=['PUT'])
def update_settings():
    data     = request.get_json()
    settings = read_json('settings.json') or {}
    settings.update(data)
    write_json('settings.json', settings)
    return jsonify(settings)


@bp.route('/api/settings/triage-question', methods=['GET'])
def get_triage_question():
    s = read_json('settings.json') or {}
    return jsonify({'question': s.get('inbox_triage_question',
        'If you had one more year of productive work left, would you spend any of it on this?')})


@bp.route('/api/settings/triage-question', methods=['PUT'])
def update_triage_question():
    data = request.get_json()
    s    = read_json('settings.json') or {}
    s['inbox_triage_question'] = data.get('question', '')
    write_json('settings.json', s)
    return jsonify({'ok': True})


@bp.route('/api/settings/constants', methods=['GET'])
def get_settings_constants():
    return jsonify(get_constants())


@bp.route('/api/settings/constants', methods=['PUT'])
def update_settings_constants():
    data    = request.get_json()
    s       = read_json('settings.json') or {}
    allowed = set(_DEFAULTS.keys())
    for k, v in data.items():
        if k in allowed:
            try:
                s[k] = int(v)
            except (ValueError, TypeError):
                return jsonify({'error': f'Invalid value for {k}: must be integer'}), 400
    write_json('settings.json', s)
    return jsonify(get_constants())


# ── Plugins ───────────────────────────────────────────────────────────────────

@bp.route('/api/plugins', methods=['GET'])
def list_plugins():
    from app import _plugins
    settings = read_json('settings.json') or {}
    enabled  = settings.get('plugins_enabled', {})
    return jsonify([{
        'name':        p.name,
        'label':       p.label,
        'description': p.description,
        'enabled':     enabled.get(p.name, True),
        'actions':     p.get_ui_actions(),
    } for p in _plugins.values()])


@bp.route('/api/plugins/<plugin_name>/execute', methods=['POST'])
def execute_plugin(plugin_name):
    from app import _plugins
    if plugin_name not in _plugins:
        return jsonify({'error': f'Plugin "{plugin_name}" not found'}), 404
    plugin  = _plugins[plugin_name]
    payload = request.get_json() or {}
    data    = {
        'projects':         read_json('projects.json') or [],
        'content_pipeline': read_json('content_pipeline.json') or [],
        'lead_measures':    read_json('lead_measures.json') or {},
        'settings':         read_json('settings.json') or {},
        'params':           payload.get('params', {}),
    }
    try:
        result = plugin.execute(payload.get('action'), data)
        return jsonify({'ok': True, 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Pipeline Overview (Phase 3) ───────────────────────────────────────────────

@bp.route('/api/pipeline/overview')
def api_pipeline_overview():
    pipeline = read_json('content_pipeline.json') or []

    WORK_TYPES  = ['Book', 'Podcast', 'Fundraising Campaign', 'Retreat (Event)']
    STAGES      = ['producing', 'publishing', 'promoting']

    def count_by_type(stage):
        breakdown = {wt: 0 for wt in WORK_TYPES}
        for e in pipeline:
            if e.get('workflow_stage') == stage:
                wt = e.get('work_type', 'Book')
                breakdown[wt] = breakdown.get(wt, 0) + 1
        total = sum(breakdown.values())
        return {'total': total, 'breakdown': breakdown}

    counts = {s: count_by_type(s) for s in STAGES}

    # Modules list for drill-down
    modules = [
        {
            'id':         e.get('id'),
            'title':      e.get('chapter', ''),
            'work_name':  e.get('book', ''),
            'work_type':  e.get('work_type', 'Book'),
            'workflow_stage': e.get('workflow_stage', 'producing'),
        }
        for e in pipeline
    ]

    return jsonify({'counts': counts, 'modules': modules})


# ── Frontend ──────────────────────────────────────────────────────────────────

@bp.route('/')
def home():
    return redirect(url_for('core.mode_pipeline'))


@bp.route('/pipeline')
def mode_pipeline():
    return render_template('index.html')


@bp.route('/works')
def mode_works():
    return render_template('index.html')


@bp.route('/promote')
def mode_promote():
    return render_template('index.html')
