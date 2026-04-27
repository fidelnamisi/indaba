"""
ROADMAP.md idea capture — appends ideas with timestamps, then git-commits and pushes.
"""
import os
import subprocess
from datetime import datetime, timezone, timedelta

SAST = timezone(timedelta(hours=2))
from config import ROADMAP_FILE, REPO_DIR, GITHUB_TOKEN


def add_idea(text: str) -> str:
    """
    Append an idea to ROADMAP.md and push to GitHub.
    Returns a status string for Discord display.
    """
    timestamp = datetime.now(SAST).strftime("%Y-%m-%d %H:%M SAST")
    entry = f"\n- **{timestamp}** — {text.strip()}\n"

    # Ensure ROADMAP.md exists
    if not os.path.exists(ROADMAP_FILE):
        with open(ROADMAP_FILE, "w") as f:
            f.write("# Indaba Roadmap & Wishlist\n\n"
                    "Ideas captured from Discord, ordered by date added.\n\n"
                    "## Ideas\n")

    # Append the idea
    with open(ROADMAP_FILE, "a") as f:
        f.write(entry)

    # Git commit + push
    push_status = _git_push(f"roadmap: {text[:60]}")
    return push_status


def _git_push(commit_msg: str) -> str:
    """Commit ROADMAP.md and push. Returns a short status string."""
    try:
        env = os.environ.copy()
        if GITHUB_TOKEN:
            # Embed token in remote URL for HTTPS push
            remote_url = _get_remote_url()
            if remote_url and remote_url.startswith("https://github.com/"):
                path = remote_url.replace("https://github.com/", "")
                authed_url = f"https://{GITHUB_TOKEN}@github.com/{path}"
                _run(["git", "remote", "set-url", "origin", authed_url], env=env)

        _run(["git", "add", "ROADMAP.md"], env=env)
        _run(["git", "commit", "-m", commit_msg], env=env)

        if GITHUB_TOKEN:
            _run(["git", "push", "origin", "main"], env=env)
            return "saved to ROADMAP.md and pushed to GitHub"
        else:
            return "saved to ROADMAP.md (committed locally — add GITHUB_TOKEN to push)"
    except subprocess.CalledProcessError as e:
        return f"saved to ROADMAP.md but git error: {e.stderr or str(e)}"


def _run(cmd: list, env: dict | None = None):
    result = subprocess.run(
        cmd, cwd=REPO_DIR, capture_output=True, text=True, env=env
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr
        )
    return result.stdout


def _get_remote_url() -> str:
    try:
        return _run(["git", "remote", "get-url", "origin"]).strip()
    except Exception:
        return ""
