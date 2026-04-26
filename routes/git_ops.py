"""
Git operations — push Indaba source to GitHub.
"""
import subprocess
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from utils.json_store import BASE_DIR

bp = Blueprint('git_ops', __name__)


@bp.route('/api/git/push', methods=['POST'])
def git_push():
    """Stage all changes, commit with timestamp, push to origin main."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    commit_msg = f'Auto-push from Indaba — {now}'

    def run(cmd):
        return subprocess.run(
            cmd, cwd=BASE_DIR, capture_output=True, text=True, timeout=60
        )

    try:
        # Stage everything
        add = run(['git', 'add', '-A'])
        if add.returncode != 0:
            return jsonify({'ok': False, 'error': add.stderr.strip() or 'git add failed'}), 500

        # Check if there's anything to commit
        status = run(['git', 'status', '--porcelain'])
        if not status.stdout.strip():
            # Nothing to commit — just push whatever's already committed
            push = run(['git', 'push', 'origin', 'main'])
            if push.returncode != 0:
                return jsonify({'ok': False, 'error': push.stderr.strip() or 'git push failed'}), 500
            return jsonify({'ok': True, 'message': 'Nothing to commit — pushed existing commits.', 'output': push.stdout.strip()})

        # Commit
        commit = run(['git', 'commit', '-m', commit_msg])
        if commit.returncode != 0:
            return jsonify({'ok': False, 'error': commit.stderr.strip() or 'git commit failed'}), 500

        # Push
        push = run(['git', 'push', 'origin', 'main'])
        if push.returncode != 0:
            return jsonify({'ok': False, 'error': push.stderr.strip() or 'git push failed'}), 500

        return jsonify({'ok': True, 'message': f'Pushed to GitHub. Commit: {commit_msg}', 'output': push.stdout.strip()})

    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'error': 'Git operation timed out'}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
