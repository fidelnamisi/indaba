"""
Agentic Claude loop for the Indaba Discord Bot.

Every natural-language message runs through a tool-use loop:
  user message → Claude picks tools → tools call Indaba API → Claude replies

Claude keeps calling tools until it has enough information to give a final answer.
All Indaba read AND write operations are available as tools.
"""
import json
import anthropic
import indaba_client as api
import roadmap
from config import ANTHROPIC_API_KEY, AI_MODEL

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "hub_summary",
        "description": "Get the Indaba pipeline overview: counts of entries per stage (producing/publishing/promoting) and promo stats.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "pipeline_list",
        "description": "List pipeline entries. Optionally filter by book code or stage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "book":  {"type": "string", "description": "Book code: LB, OAO, ROTRQ, MOSAS. Leave empty for all."},
                "stage": {"type": "string", "description": "producing | publishing | promoting. Leave empty for all."},
            },
        },
    },
    {
        "name": "pipeline_get",
        "description": "Get full details of a single pipeline entry by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string", "description": "Pipeline entry ID, e.g. 'love-back-ch2-pipeline'"},
            },
            "required": ["entry_id"],
        },
    },
    {
        "name": "pipeline_set_stage",
        "description": "Move a pipeline entry to a different workflow stage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string"},
                "stage":    {"type": "string", "enum": ["producing", "publishing", "promoting"]},
            },
            "required": ["entry_id", "stage"],
        },
    },
    {
        "name": "website_publish",
        "description": "Publish a single pipeline entry as a static HTML page on realmsandroads.com. Entry must have blurb, tagline, and prose.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_id": {"type": "string"},
            },
            "required": ["entry_id"],
        },
    },
    {
        "name": "website_deploy",
        "description": "Deploy the local website to AWS Amplify so changes go live. Takes ~2 minutes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "website_deploy_status",
        "description": "Check the current status of the website deployment (idle/deploying/deployed/failed).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "website_work_sync",
        "description": "Compare Indaba's pipeline with what's live on the website for a given work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "work_id": {"type": "string", "description": "Series code, e.g. LB"},
            },
            "required": ["work_id"],
        },
    },
    {
        "name": "works_list",
        "description": "List all book series / works in the catalog.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "ec2_sender_health",
        "description": "Check EC2 WhatsApp sender health: queue length, device connection status.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "promo_broadcast_list",
        "description": "List all proverbs in the proverb library, including their IDs and whether a broadcast post has been generated for them.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "promo_broadcast_generate",
        "description": "Generate an AI-written broadcast post (caption + image prompt) for a proverb. Must be called before queuing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proverb_id": {"type": "string", "description": "ID of the proverb from promo_broadcast_list"},
            },
            "required": ["proverb_id"],
        },
    },
    {
        "name": "promo_broadcast_queue",
        "description": "Queue a generated broadcast post for delivery to the WhatsApp channel via EC2 sender.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proverb_id": {"type": "string"},
                "channel":    {"type": "string", "default": "channel", "description": "Delivery channel. Default: channel."},
            },
            "required": ["proverb_id"],
        },
    },
    {
        "name": "generate_asset",
        "description": "Generate an AI asset (synopsis, blurb, tagline, or image_prompt) for a pipeline entry. Generate synopsis first — blurb/tagline/image_prompt use it as input.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry_id":   {"type": "string"},
                "asset_type": {"type": "string", "enum": ["synopsis", "blurb", "tagline", "image_prompt"]},
            },
            "required": ["entry_id", "asset_type"],
        },
    },
    {
        "name": "settings_get",
        "description": "Get current Indaba settings (website dir, AI provider, etc.).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_roadmap_idea",
        "description": "Save an idea or feature request to ROADMAP.md and push to GitHub.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The idea, verbatim."},
            },
            "required": ["text"],
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

def _execute_tool(name: str, inputs: dict) -> str:
    """Call the matching Indaba API function and return JSON string result."""
    try:
        if name == "hub_summary":
            return json.dumps(api.hub_summary())
        elif name == "pipeline_list":
            return json.dumps(api.pipeline_list(inputs.get("book", ""), inputs.get("stage", "")))
        elif name == "pipeline_get":
            return json.dumps(api.pipeline_get(inputs["entry_id"]))
        elif name == "pipeline_set_stage":
            return json.dumps(api.pipeline_set_stage(inputs["entry_id"], inputs["stage"]))
        elif name == "website_publish":
            return json.dumps(api.website_publish(inputs["entry_id"]))
        elif name == "website_deploy":
            return json.dumps(api.website_deploy())
        elif name == "website_deploy_status":
            return json.dumps(api.website_deploy_status())
        elif name == "website_work_sync":
            return json.dumps(api.website_work_sync(inputs["work_id"]))
        elif name == "works_list":
            return json.dumps(api.works_list())
        elif name == "ec2_sender_health":
            return json.dumps(api.ec2_sender_health())
        elif name == "promo_broadcast_list":
            return json.dumps(api.promo_broadcast_list())
        elif name == "promo_broadcast_generate":
            return json.dumps(api.promo_broadcast_generate(inputs["proverb_id"]))
        elif name == "promo_broadcast_queue":
            return json.dumps(api.promo_broadcast_queue(inputs["proverb_id"], inputs.get("channel", "channel")))
        elif name == "generate_asset":
            return json.dumps(api.generate_asset(inputs["entry_id"], inputs["asset_type"]))
        elif name == "settings_get":
            return json.dumps(api.settings_get())
        elif name == "add_roadmap_idea":
            result = roadmap.add_idea(inputs["text"])
            return json.dumps({"ok": True, "status": result})
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Indaba Bot, the AI operator for Fidel Namisi's publishing dashboard.

Fidel is a professional author publishing African fantasy fiction. You help him manage his content pipeline, publish chapters, and run his WhatsApp promo channel.

Your job: understand what Fidel wants and use your tools to make it happen. For multi-step tasks (e.g. "generate and queue 5 proverbs"), plan the steps, execute them in sequence using tools, and report back with a clear summary.

Rules:
- Always use tools to get real data before answering questions about pipeline state.
- For "create and queue" tasks: generate first, then queue.
- Keep responses concise. Use bullet points for lists of results.
- If a task partially fails, complete what you can and report what failed.
- Book codes: LB=Love Back, OAO=Outlaws and Outcasts, ROTRQ=Rise of the Rain Queen, MOSAS=Mothers of Suns and Stars
- Stages: producing → publishing → promoting
"""


# ── Agentic loop ──────────────────────────────────────────────────────────────

def run_agent(user_message: str, progress_callback=None) -> str:
    """
    Run the full agentic loop for a user message.

    progress_callback(text): called with intermediate status messages
    so the Discord bot can show "Calling promo_broadcast_generate..." etc.

    Returns the final text response from Claude.
    """
    if not ANTHROPIC_API_KEY:
        return "ANTHROPIC_API_KEY not set — cannot process requests."

    client = _get_client()
    messages = [{"role": "user", "content": user_message}]

    for _ in range(20):  # max 20 tool-call rounds
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            # Extract final text
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "Done."

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    if progress_callback:
                        progress_callback(f"  `{block.name}`…")
                    result = _execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return "Reached tool call limit without a final answer."
