"""
Indaba — modular monolith entry point.
Registers all blueprints, loads plugins, runs migrations, starts server.
"""
import os
import importlib
import pkgutil

from flask import Flask, send_from_directory

from utils.json_store import BASE_DIR
from utils.migrate import migrate, sync_existing_data_to_assets, retry_failed_messages

# ── App factory ───────────────────────────────────────────────────────────────

app = Flask(__name__)

# ── Plugin registry (imported by routes.core) ─────────────────────────────────

_plugins = {}


def load_plugins():
    import sys
    sys.path.insert(0, BASE_DIR)
    plugins_pkg = os.path.join(BASE_DIR, 'plugins')
    for finder, name, _ in pkgutil.iter_modules([plugins_pkg]):
        try:
            module   = importlib.import_module(f'plugins.{name}')
            if hasattr(module, 'PLUGIN_CLASS'):
                instance             = module.PLUGIN_CLASS()
                _plugins[instance.name] = instance
        except Exception as e:
            print(f'[Indaba] Failed to load plugin "{name}": {e}')


# ── Blueprint registration ────────────────────────────────────────────────────

def register_blueprints():
    from routes.core           import bp as core_bp
    from routes.assets         import bp as assets_bp
    from routes.pipeline       import bp as pipeline_bp
    from routes.crm            import bp as crm_bp
    from routes.promo_contacts import bp as promo_contacts_bp
    from routes.promo_leads    import bp as promo_leads_bp
    from routes.works          import bp as works_bp
    from routes.promo_messages import bp as promo_messages_bp
    from routes.promo_sender   import bp as promo_sender_bp
    from routes.promo_proverbs import bp as promo_proverbs_bp
    from routes.promo_broadcast_post import bp as promo_broadcast_post_bp
    from routes.promo_settings import bp as promo_settings_bp
    from routes.publishing         import bp as publishing_bp
    from routes.website_publisher  import bp as website_publisher_bp
    from routes.asset_register     import bp as asset_register_bp
    from routes.work_types         import bp as work_types_bp
    from routes.audio              import bp as audio_bp
    from routes.flash_fiction      import bp as flash_fiction_bp
    from routes.scheduler_agent    import bp as scheduler_agent_bp
    from routes.crm_people         import bp as crm_people_bp
    from routes.git_ops            import bp as git_ops_bp
    from routes.macos_contacts     import bp as macos_contacts_bp

    for bp in [
        core_bp, assets_bp,
        pipeline_bp, crm_bp, promo_contacts_bp, promo_leads_bp,
        works_bp, promo_messages_bp, promo_sender_bp,
        promo_proverbs_bp, promo_broadcast_post_bp, promo_settings_bp,
        publishing_bp, website_publisher_bp, asset_register_bp, work_types_bp,
        audio_bp, flash_fiction_bp, scheduler_agent_bp, crm_people_bp,
        git_ops_bp, macos_contacts_bp,
    ]:
        app.register_blueprint(bp)


# ── Static file serving ───────────────────────────────────────────────────────

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)


@app.route('/data/images/<path:filename>')
def serve_generated_image(filename):
    """Serve generated header images — used by GOWA (via host.docker.internal) to fetch images."""
    return send_from_directory(os.path.join(BASE_DIR, 'data', 'generated_images'), filename)


register_blueprints()


def _migrate_synopsis_to_modules():
    """Ensure every existing pipeline module has all register-defined supporting assets."""
    from utils.json_store import read_json, write_json
    from routes.asset_register import supporting_keys_for_work_type
    pipeline = read_json('content_pipeline.json') or []
    changed = False
    for entry in pipeline:
        work_type = entry.get('work_type', 'Book')
        ps = entry.setdefault('producing_status', {})
        sa = ps.setdefault('supporting_assets', {})
        for key in supporting_keys_for_work_type(work_type):
            if key not in sa:
                sa[key] = 'missing'
                changed = True
    if changed:
        write_json('content_pipeline.json', pipeline)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import socket
    import threading
    import webbrowser

    def find_free_port(preferred=5050, max_tries=20):
        for port in range(preferred, preferred + max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('', port))
                    return port
                except OSError:
                    continue
        raise RuntimeError(f'No free port found in range {preferred}–{preferred + max_tries}')

    # Load shell environment to pick up API keys
    try:
        import subprocess as _sp
        _env_out = _sp.check_output(
            'source ~/.zshrc && env', shell=True, executable='/bin/zsh'
        ).decode()
        for _line in _env_out.splitlines():
            if '=' in _line:
                _k, _, _v = _line.partition('=')
                if _k not in os.environ:
                    os.environ[_k] = _v
    except Exception as _e:
        print(f'[Env load warning] {_e}')

    load_plugins()
    migrate()
    _migrate_synopsis_to_modules()
    retry_failed_messages()
    sync_existing_data_to_assets()

    port = find_free_port(5050)
    url  = f'http://localhost:{port}'

    print('\n  ┌──────────────────────────────────┐')
    print('  │   INDABA — Morning Briefing       │')
    print(f'  │   {url:<30}│')
    print('  └──────────────────────────────────┘')

    if port != 5050:
        print(f'\n  ⚠  Port 5050 was busy — running on port {port} instead.\n')
    else:
        print()

    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host='0.0.0.0', port=port, debug=False)
