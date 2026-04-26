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
    # ── Phase 1 tools ──────────────────────────────────────────────────────────
    {
        "name": "works_list_modules",
        "description": "Get a specific work/series with all its serialised chunks/modules. Use this to see chapters of Love Back, OAO, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "work_id": {"type": "string", "description": "The work UUID from works_list."},
            },
            "required": ["work_id"],
        },
    },
    {
        "name": "work_queue_module",
        "description": "Queue a serialised chunk/module for WhatsApp delivery. Optionally include a website CTA URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "work_id":    {"type": "string", "description": "Work UUID"},
                "module_id":  {"type": "string", "description": "Chunk UUID"},
                "cta_url":    {"type": "string", "description": "Optional website URL to append as a CTA link."},
            },
            "required": ["work_id", "module_id"],
        },
    },
    {
        "name": "scheduler_run",
        "description": "Execute the 14-day rolling content scheduler — assigns unqueued proverbs, novel serial chunks, and flash fiction to their canonical slots.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dry_run": {"type": "boolean", "description": "If true, preview without writing. Default: false."},
            },
        },
    },
    {
        "name": "scheduler_preview",
        "description": "Preview what the scheduler would queue over the next 14 days without making any changes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "proverbs_create_batch",
        "description": "Bulk-import a list of new proverbs into the proverb library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proverbs": {
                    "type": "array",
                    "description": "List of proverb objects. Each must have 'text'; 'origin' is optional.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text":   {"type": "string"},
                            "origin": {"type": "string"},
                        },
                        "required": ["text"],
                    },
                },
            },
            "required": ["proverbs"],
        },
    },
    {
        "name": "flash_fiction_generate",
        "description": "Generate a complete piece of AI flash fiction. Requires genre, trope, twist, setting fields, and word_count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "genre":               {"type": "string", "enum": ["historical", "romance", "fantasy", "science_fiction", "thriller", "horror"]},
                "trope":               {"type": "string", "description": "Trope key, e.g. 'chosen_one', 'dark_bargain', 'second_chance'"},
                "twist":               {"type": "string", "enum": ["invert_outcome", "shift_victim", "reveal_cause", "reframe_genre", "compress_timeline", "relocate_monster", "collapse_archetype"]},
                "setting_place":       {"type": "string", "description": "Specific place, e.g. 'Lagos, 1967'"},
                "setting_era":         {"type": "string", "description": "Time period or era"},
                "setting_atmosphere":  {"type": "string", "description": "Dominant atmosphere, e.g. 'rain-soaked dread'"},
                "word_count":          {"type": "string", "enum": ["100_300", "300_500", "500_750", "750_1000"]},
                "pov":                 {"type": "string", "enum": ["first_person", "third_person_limited", "unreliable_narrator"]},
                "character":           {"type": "string", "description": "Optional: brief description of central character"},
                "emotion":             {"type": "string", "enum": ["dread", "ache", "exhilaration", "unease", "tenderness", "shock"]},
                "constraint":          {"type": "string", "description": "Optional: specific writing constraint"},
            },
            "required": ["genre", "trope", "twist", "setting_place", "setting_era", "setting_atmosphere", "word_count"],
        },
    },
    {
        "name": "flash_fiction_publish_queue",
        "description": "Publish a pipeline entry to the website, then queue a work module for WhatsApp delivery with the website URL as a CTA. Use after flash fiction is ready in the pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_entry_id": {"type": "string", "description": "Pipeline entry ID to publish to the website"},
                "work_id":           {"type": "string", "description": "Work UUID for the WA queue"},
                "module_id":         {"type": "string", "description": "Module/chunk UUID to queue"},
            },
            "required": ["pipeline_entry_id", "work_id", "module_id"],
        },
    },
    {
        "name": "audio_browse",
        "description": "List MP3 audio files available in the pCloud folder for a given work/series.",
        "input_schema": {
            "type": "object",
            "properties": {
                "work_id": {"type": "string", "description": "Series code or UUID, e.g. OAO, LB"},
            },
            "required": ["work_id"],
        },
    },
    {
        "name": "audio_upload",
        "description": "Upload a local pCloud MP3 file to S3 and link it to a pipeline module. Returns a job_id to poll for progress.",
        "input_schema": {
            "type": "object",
            "properties": {
                "work_id":        {"type": "string", "description": "Series code, e.g. OAO"},
                "filename":       {"type": "string", "description": "MP3 filename from audio_browse"},
                "module_id":      {"type": "string", "description": "Pipeline entry ID to link the audio to"},
                "chapter_number": {"type": "integer", "description": "Optional: override chapter number for S3 key"},
            },
            "required": ["work_id", "filename", "module_id"],
        },
    },
    {
        "name": "crm_leads_summary",
        "description": "Get a summary of the CRM pipeline: all leads grouped by stage (lead, pitched, negotiating, closed, lost).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # ── Phase 3 tools ──────────────────────────────────────────────────────────
    {
        "name": "proverbs_generate_batch",
        "description": "Generate AI captions and images for the next N proverbs in the library that don't yet have a broadcast post. Use this to batch-process unfinished proverbs so they can be scheduled.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of proverbs to process (default 10, max 50)"},
            },
            "required": [],
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
        # ── Phase 1 tools ──────────────────────────────────────────────────────
        elif name == "works_list_modules":
            return json.dumps(api.works_get(inputs["work_id"]))
        elif name == "work_queue_module":
            return json.dumps(api.work_queue_module(
                inputs["work_id"], inputs["module_id"],
                cta_url=inputs.get("cta_url", "")
            ))
        elif name == "scheduler_run":
            return json.dumps(api.scheduler_run(dry_run=inputs.get("dry_run", False)))
        elif name == "scheduler_preview":
            return json.dumps(api.scheduler_preview())
        elif name == "proverbs_create_batch":
            return json.dumps(api.proverbs_create_batch(inputs["proverbs"]))
        elif name == "flash_fiction_generate":
            return json.dumps(api.flash_fiction_generate(inputs))
        elif name == "flash_fiction_publish_queue":
            return json.dumps(api.flash_fiction_publish_queue(
                inputs["pipeline_entry_id"], inputs["work_id"], inputs["module_id"]
            ))
        elif name == "audio_browse":
            return json.dumps(api.audio_browse(inputs["work_id"]))
        elif name == "audio_upload":
            return json.dumps(api.audio_upload(
                inputs["work_id"], inputs["filename"], inputs["module_id"],
                chapter_number=inputs.get("chapter_number")
            ))
        elif name == "crm_leads_summary":
            return json.dumps(api.crm_leads_summary())
        # ── Phase 3 tools ──────────────────────────────────────────────────────
        elif name == "proverbs_generate_batch":
            return json.dumps(api.proverbs_generate_batch(inputs.get("limit", 10)))
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
