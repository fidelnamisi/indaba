# Indaba MCP Server

Gives Claude native programmatic access to all Indaba operations as proper MCP tools.

## Install

```bash
cd /Users/fidelnamisi/Indaba/mcp
pip install -r requirements.txt
```

## Register with Claude Code

Add this to `~/.claude/claude_desktop_config.json` (create if it doesn't exist):

```json
{
  "mcpServers": {
    "indaba": {
      "command": "python",
      "args": ["/Users/fidelnamisi/Indaba/mcp/server.py"],
      "env": {}
    }
  }
}
```

Or if you use `python3`:
```json
{
  "mcpServers": {
    "indaba": {
      "command": "python3",
      "args": ["/Users/fidelnamisi/Indaba/mcp/server.py"],
      "env": {}
    }
  }
}
```

Restart Claude Code after editing the config.

## Prerequisites

Indaba must be running on port 5050 before using any tools:
```bash
cd /Users/fidelnamisi/Indaba
python launch.py
```

## Available Tools

| Tool | What it does |
|------|-------------|
| `hub_summary` | Pipeline overview — counts, pending tasks |
| `pipeline_list` | List entries (filter by book/stage) |
| `pipeline_get` | Get a single entry |
| `pipeline_update` | Update any fields |
| `pipeline_add` | Create a new entry |
| `pipeline_delete` | Delete an entry |
| `pipeline_set_stage` | Move to producing/publishing/promoting |
| `pipeline_update_producing_status` | Mark assets done/missing |
| `pipeline_update_publishing_status` | Update per-platform status |
| `generate_asset` | AI-generate synopsis/blurb/tagline/image_prompt |
| `website_publish` | Publish chapter to local website |
| `website_publish_batch` | Publish multiple chapters |
| `website_deploy` | Deploy to Amplify (goes live) |
| `website_deploy_status` | Check deployment progress |
| `website_work_sync` | Compare Indaba vs live website |
| `works_list` | List all works/series |
| `works_create` | Create a new work |
| `flash_fiction_generate` | Generate a flash fiction story |
| `queue_wa_message` | Queue a WA message (EC2 outbox) |
| `promo_broadcast_generate` | Generate a broadcast post |
| `promo_broadcast_queue` | Queue a broadcast post |
| `promo_broadcast_list` | List proverbs for broadcast |
| `settings_get` | View current settings |
| `settings_update` | Update settings |
