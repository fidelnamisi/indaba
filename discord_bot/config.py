"""
Indaba Discord Bot — configuration.
All values are read from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Discord ───────────────────────────────────────────────────────────────────
DISCORD_TOKEN        = os.environ.get("DISCORD_BOT_TOKEN", "")
INDABA_CHANNEL_NAME  = os.environ.get("INDABA_CHANNEL", "indaba-ops")

# ── Indaba API ────────────────────────────────────────────────────────────────
INDABA_BASE_URL      = os.environ.get("INDABA_BASE_URL", "http://localhost:5050")

# ── AI (Claude Haiku for NLP parsing) ────────────────────────────────────────
ANTHROPIC_API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")
AI_MODEL             = "claude-haiku-4-5-20251001"

# ── Git / ROADMAP ─────────────────────────────────────────────────────────────
REPO_DIR             = os.environ.get("INDABA_REPO_DIR", "/opt/indaba-app")
ROADMAP_FILE         = os.path.join(REPO_DIR, "ROADMAP.md")
GITHUB_TOKEN         = os.environ.get("GITHUB_TOKEN", "")
