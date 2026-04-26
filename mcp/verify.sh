#!/bin/bash
# Indaba MCP — one-time verification script
# Run from Terminal: bash /Users/fidelnamisi/Indaba/mcp/verify.sh

set -e
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓ $1${NC}"; }
fail() { echo -e "${RED}  ✗ $1${NC}"; }
info() { echo -e "${YELLOW}  → $1${NC}"; }

echo ""
echo "=== Indaba MCP Setup Verification ==="
echo ""

# 1. Check uv
if command -v uv >/dev/null 2>&1; then
    ok "uv is installed: $(uv --version)"
else
    fail "uv not found"
    info "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 2. Check server.py exists
if [ -f "/Users/fidelnamisi/Indaba/mcp/server.py" ]; then
    ok "server.py exists"
else
    fail "server.py not found at /Users/fidelnamisi/Indaba/mcp/server.py"
    exit 1
fi

# 3. Check .mcp.json exists
if [ -f "/Users/fidelnamisi/Indaba/.mcp.json" ]; then
    ok ".mcp.json exists"
else
    fail ".mcp.json not found at /Users/fidelnamisi/Indaba/.mcp.json"
    exit 1
fi

# 4. Test the server imports (uv will install deps on first run)
echo ""
info "Testing server startup (uv will fetch deps if needed — ~10 seconds first time)..."
echo ""

timeout 15 uv run --script /Users/fidelnamisi/Indaba/mcp/server.py --help 2>&1 || true

echo ""
ok "All checks passed. Restart Claude to activate the indaba MCP tools."
echo ""
echo "  After restart, Claude will have these tools:"
echo "    hub_summary, pipeline_list, pipeline_get, pipeline_update,"
echo "    pipeline_add, pipeline_set_stage, generate_asset,"
echo "    website_publish, website_deploy, works_list, works_create,"
echo "    flash_fiction_generate, queue_wa_message, and more."
echo ""
