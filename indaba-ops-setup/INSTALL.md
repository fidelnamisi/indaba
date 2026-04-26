# One-time setup — run these in Terminal

```bash
# Create the ops workspace directory
mkdir -p ~/Indaba-ops

# Copy the two config files into it
cp ~/Indaba/indaba-ops-setup/CLAUDE.md ~/Indaba-ops/CLAUDE.md
cp ~/Indaba/indaba-ops-setup/.mcp.json ~/Indaba-ops/.mcp.json

# Verify uv is installed (needed to run the MCP server)
uv --version
# If not installed: curl -LsSf https://astral.sh/uv/install.sh | sh

# Test the MCP server starts (uv will fetch deps on first run)
uv run --script ~/Indaba/mcp/server.py --help
```

## You now have two Claude Code workspaces:

| Purpose | Command |
|---------|---------|
| Build Indaba (code, fix, extend) | `cd ~/Indaba && claude` |
| Operate Indaba (publish, pipeline, deploy) | `cd ~/Indaba-ops && claude` |

## The ops workspace needs Indaba running first:
```bash
# In a separate Terminal tab — keep this running
cd ~/Indaba && python launch.py
```

Then in another tab:
```bash
cd ~/Indaba-ops && claude
```
