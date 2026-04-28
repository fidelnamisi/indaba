"""
Audio routes — browse pCloud via API and link files directly to modules.
No local pCloud mount or S3 upload needed; files are linked by pCloud file ID.
"""
import os
import secrets

import requests
from flask import Blueprint, jsonify, request

from utils.json_store import read_json, write_json

bp = Blueprint('audio', __name__)

PCLOUD_CLIENT_ID     = '7gwpWvnAYR0'
PCLOUD_CLIENT_SECRET = 'CHaPsGVcTgVIm6FN4f0MVJA9Iuk7'
PCLOUD_TOKEN_FILE    = 'pcloud_token.json'

# In-memory state nonces for OAuth
_oauth_states = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_token():
    """Return (access_token, hostname) or (None, None)."""
    data = read_json(PCLOUD_TOKEN_FILE) or {}
    return data.get('access_token'), data.get('hostname', 'api.pcloud.com')


def _save_token(access_token, hostname):
    write_json(PCLOUD_TOKEN_FILE, {'access_token': access_token, 'hostname': hostname})


def _pcloud_get(endpoint, params, token=None, hostname=None):
    """Authenticated GET to pCloud API. Raises on HTTP error."""
    if token is None:
        token, hostname = _load_token()
    if not hostname:
        hostname = 'api.pcloud.com'
    url = f'https://{hostname}/{endpoint}'
    params['access_token'] = token
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

@bp.route('/api/audio/pcloud/status', methods=['GET'])
def pcloud_status():
    """Check whether pCloud is connected (valid token)."""
    token, hostname = _load_token()
    if not token:
        return jsonify({'connected': False})
    try:
        info = _pcloud_get('userinfo', {}, token=token, hostname=hostname)
        if info.get('result', 0) != 0:
            return jsonify({'connected': False, 'error': info.get('error', 'Token invalid')})
        return jsonify({'connected': True, 'email': info.get('email', ''), 'hostname': hostname})
    except Exception as e:
        return jsonify({'connected': False, 'error': str(e)})


@bp.route('/api/audio/pcloud/auth', methods=['GET'])
def pcloud_auth():
    """Return an OAuth authorization URL for the user to visit."""
    redirect_base = os.environ.get('PCLOUD_REDIRECT_BASE', 'http://localhost:5050')
    redirect_uri  = f'{redirect_base}/api/audio/pcloud/callback'
    state = secrets.token_hex(16)
    _oauth_states[state] = True
    auth_url = (
        'https://my.pcloud.com/oauth2/authorize'
        f'?client_id={PCLOUD_CLIENT_ID}'
        f'&response_type=code'
        f'&redirect_uri={requests.utils.quote(redirect_uri, safe="")}'
        f'&state={state}'
    )
    return jsonify({'auth_url': auth_url, 'redirect_uri': redirect_uri})


@bp.route('/api/audio/pcloud/callback', methods=['GET'])
def pcloud_callback():
    """Handle OAuth redirect from pCloud, exchange code for token."""
    code  = request.args.get('code', '')
    state = request.args.get('state', '')
    if state not in _oauth_states:
        return '<h2>Error: Invalid or expired state. Please try again from Indaba.</h2>', 400
    del _oauth_states[state]

    redirect_base = os.environ.get('PCLOUD_REDIRECT_BASE', 'http://localhost:5050')
    redirect_uri  = f'{redirect_base}/api/audio/pcloud/callback'
    try:
        resp = requests.get(
            'https://api.pcloud.com/oauth2_token',
            params={
                'client_id':     PCLOUD_CLIENT_ID,
                'client_secret': PCLOUD_CLIENT_SECRET,
                'code':          code,
                'redirect_uri':  redirect_uri,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get('result', 0) != 0 or 'access_token' not in data:
            return f'<h2>pCloud OAuth failed: {data.get("error", "Unknown error")}</h2>', 400
        hostname = data.get('hostname', 'api.pcloud.com')
        _save_token(data['access_token'], hostname)
        return (
            '<html><body style="font-family:sans-serif;text-align:center;padding:40px;">'
            '<h2 style="color:#27ae60">pCloud connected successfully!</h2>'
            '<p>You can close this tab and return to Indaba.</p>'
            '<script>setTimeout(()=>window.close(),2000);</script>'
            '</body></html>'
        )
    except Exception as e:
        return f'<h2>Error connecting pCloud: {e}</h2>', 500


# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------

@bp.route('/api/audio/pcloud/browse', methods=['GET'])
def pcloud_browse():
    """
    List folders and MP3 files in a pCloud folder.
    Query params: path (default '/') or folder_id.
    """
    token, hostname = _load_token()
    if not token:
        return jsonify({'error': 'pCloud not connected', 'needs_auth': True}), 401

    path      = request.args.get('path', '/')
    folder_id = request.args.get('folder_id')

    try:
        params = {}
        if folder_id:
            params['folderid'] = folder_id
        else:
            params['path'] = path

        data = _pcloud_get('listfolder', params, token=token, hostname=hostname)
        if data.get('result', 0) != 0:
            return jsonify({'error': data.get('error', 'Browse failed')}), 400

        meta     = data.get('metadata', {})
        contents = meta.get('contents', [])

        folders = [
            {
                'name':      item['name'],
                'folder_id': item['folderid'],
                'path':      item.get('path', ''),
            }
            for item in contents if item.get('isfolder')
        ]
        files = [
            {
                'name':    item['name'],
                'file_id': item['fileid'],
                'size':    item.get('size', 0),
            }
            for item in contents
            if not item.get('isfolder') and item['name'].lower().endswith('.mp3')
        ]

        return jsonify({
            'path':      meta.get('path', path),
            'name':      meta.get('name', ''),
            'folder_id': meta.get('folderid'),
            'folders':   folders,
            'files':     files,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Link / Stream / Unlink
# ---------------------------------------------------------------------------

@bp.route('/api/audio/pcloud/link', methods=['POST'])
def pcloud_link():
    """
    Link a pCloud file to a module.
    Body: { module_id, file_id, filename }
    Fetches an initial stream URL (valid ~24h) and stores the reference.
    """
    token, hostname = _load_token()
    if not token:
        return jsonify({'error': 'pCloud not connected', 'needs_auth': True}), 401

    body      = request.get_json() or {}
    module_id = body.get('module_id', '').strip()
    file_id   = body.get('file_id')
    filename  = body.get('filename', '').strip()

    if not module_id or not file_id:
        return jsonify({'error': 'module_id and file_id are required'}), 400

    try:
        link_data = _pcloud_get(
            'getfilelink',
            {'fileid': file_id, 'forcedownload': 0},
            token=token, hostname=hostname,
        )
        if link_data.get('result', 0) != 0:
            return jsonify({'error': link_data.get('error', 'Failed to get link')}), 400

        hosts      = link_data.get('hosts', [])
        path_      = link_data.get('path', '')
        stream_url = f'https://{hosts[0]}{path_}' if hosts else ''

        pipeline = read_json('content_pipeline.json') or []
        for entry in pipeline:
            if entry['id'] == module_id:
                entry.setdefault('assets', {})['audio'] = {
                    'type':     'pcloud',
                    'file_id':  file_id,
                    'filename': filename,
                    'hostname': hostname,
                    'url':      stream_url,
                }
                ps = entry.setdefault('producing_status', {})
                sa = ps.setdefault('supporting_assets', {})
                sa['audio'] = 'done'
                break
        write_json('content_pipeline.json', pipeline)

        return jsonify({'ok': True, 'url': stream_url, 'filename': filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/audio/pcloud/stream/<module_id>', methods=['GET'])
def pcloud_stream(module_id):
    """Fetch a fresh streaming URL for a module's linked pCloud audio."""
    token, hostname = _load_token()
    if not token:
        return jsonify({'error': 'pCloud not connected'}), 401

    pipeline = read_json('content_pipeline.json') or []
    entry    = next((e for e in pipeline if e['id'] == module_id), None)
    if not entry:
        return jsonify({'error': 'Module not found'}), 404

    audio = entry.get('assets', {}).get('audio')
    if not audio or not isinstance(audio, dict) or audio.get('type') != 'pcloud':
        return jsonify({'error': 'No pCloud audio linked'}), 404

    file_id       = audio.get('file_id')
    file_hostname = audio.get('hostname', hostname)

    try:
        link_data = _pcloud_get(
            'getfilelink',
            {'fileid': file_id, 'forcedownload': 0},
            token=token, hostname=file_hostname,
        )
        if link_data.get('result', 0) != 0:
            return jsonify({'error': link_data.get('error', 'Failed to get link')}), 400

        hosts = link_data.get('hosts', [])
        path_ = link_data.get('path', '')
        url   = f'https://{hosts[0]}{path_}' if hosts else ''
        return jsonify({'url': url, 'filename': audio.get('filename', '')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/audio/unlink/<module_id>', methods=['POST'])
def unlink_audio(module_id):
    """Remove audio link from a module."""
    pipeline = read_json('content_pipeline.json') or []
    for entry in pipeline:
        if entry['id'] == module_id:
            entry.setdefault('assets', {}).pop('audio', None)
            ps = entry.setdefault('producing_status', {})
            sa = ps.setdefault('supporting_assets', {})
            sa['audio'] = 'missing'
            break
    write_json('content_pipeline.json', pipeline)
    return jsonify({'ok': True})
