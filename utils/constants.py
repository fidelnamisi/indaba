"""
Shared constants for Indaba.
Centralises file names, defaults, prompts, and system constants.
"""
import os
from utils.json_store import BASE_DIR, DATA_DIR

# ── Directory paths ──────────────────────────────────────────────────────────

NOTES_DIR             = os.path.join(BASE_DIR, 'notes')
PLUGIN_DIR            = os.path.join(BASE_DIR, 'plugins')
GENERATED_IMAGES_DIR  = os.path.join(DATA_DIR, 'generated_images')
FONTS_DIR             = os.path.join(BASE_DIR, 'static', 'fonts')

# ── Data file names ──────────────────────────────────────────────────────────

INBOX_FILE            = 'inbox.json'
DORMANT_FILE          = 'dormant.json'
POSTING_LOG_FILE      = 'posting_log.json'
PROMO_CONTACTS_FILE   = 'promo_contacts.json'
PROMO_LEADS_FILE      = 'promo_leads.json'
PROMO_MESSAGES_FILE   = 'promo_messages.json'
PROMO_PROVERBS_FILE   = 'promo_proverbs.json'
PROMO_WORKS_FILE      = 'works.json'
PROMO_SETTINGS_FILE   = 'promo_settings.json'
PROMO_ASSETS_FILE     = 'assets.json'
LIVING_WRITER_FILE    = 'living_writer.json'
CONTENT_PIPELINE_FILE = 'content_pipeline.json'
MERGED_MODULES_FILE   = 'merged_modules.json'
PROMO_MODULES_FILE    = 'modules.json'
EARNINGS_FILE         = 'earnings.json'
EXECUTION_LOG_FILE    = 'execution_log.json'

# ── Backwards-compat aliases (used by routes still importing old names) ──────
PROMO_BOOKS_FILE    = PROMO_WORKS_FILE
PROMO_CHAPTERS_FILE = PROMO_MODULES_FILE

# ── System defaults ──────────────────────────────────────────────────────────

_DEFAULTS = {
    'inbox_max':          15,
    'dormant_max':        25,
    'inbox_expiry_days':  7,
    'total_project_cap':  8,
    'zone_cap_morning':   3,
    'zone_cap_paid_work': 3,
    'zone_cap_evening':   2,
}

INBOX_MAX         = _DEFAULTS['inbox_max']
DORMANT_MAX       = _DEFAULTS['dormant_max']
INBOX_EXPIRY_DAYS = _DEFAULTS['inbox_expiry_days']
TOTAL_PROJECT_CAP = _DEFAULTS['total_project_cap']
ZONE_CAPS         = {
    'morning':   _DEFAULTS['zone_cap_morning'],
    'paid_work': _DEFAULTS['zone_cap_paid_work'],
    'evening':   _DEFAULTS['zone_cap_evening'],
}

POSTING_PLATFORMS = ['patreon', 'website', 'vip_group', 'wa_channel']
LEAD_STAGES       = ['lead', 'qualified', 'proposal', 'negotiation', 'won', 'lost']

# ── Promo defaults ───────────────────────────────────────────────────────────

DEFAULT_PROMO_SETTINGS = {
    "publishing_wa_recipients": {
        "vip_group_id":     "",
        "vip_group_label":  "VIP WhatsApp Group",
        "channel_id":       "",
        "channel_label":    "WA Channel"
    },
    "ai_providers": {
        "message_maker":    {"provider": "deepseek", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY"},
        "work_serializer":  {"provider": "deepseek", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY"},
        "wa_post_maker":    {"provider": "deepseek", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY"},
        "crm_assist":       {"provider": "deepseek", "model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY"},
        "image_gen":        {"provider": "", "model": "", "api_key_env": "", "endpoint": ""}
    },
    "cta_links": {
        "patreon_url": "",
        "website_url": ""
    },
    "serializer_profiles": [
        {"id": "profile-flash",  "name": "Flash Fiction",   "num_chunks": 2,    "target_words": 150},
        {"id": "profile-short",  "name": "Short Story",     "num_chunks": 3,    "target_words": 200},
        {"id": "profile-novel",  "name": "Novel Chapter",   "num_chunks": None, "target_words": 300},
    ],
    "wa_channel_branding": {
        "channel_name":        "",
        "channel_description": "",
        "cta_emoji":           "👇",
        "cta_text":            "React with an emoji if this resonated with you."
    },
    "max_leads_per_contact": 10
}

# ── AI prompts ───────────────────────────────────────────────────────────────

MESSAGE_MAKER_SYSTEM_PROMPT = """You are a WhatsApp message writer for a \
South African author and content creator.
Write a single WhatsApp message that achieves the following purpose: \
{purpose}.
Tone: warm, direct, personal. Never corporate. Never salesy.
Length: 50-120 words maximum.
Structure: 1 opening hook sentence. 1-2 sentences of context. \
1 clear call to action.
No emojis unless specified. No bullet points. Plain conversational prose.
End with a single specific action the recipient should take.
Return only the message text. No preamble. No explanation."""

CHAPTER_SYNOPSIS_PROMPT = """You are a literary editor. Write a concise synopsis for this chapter.

Rules:
- 80-150 words
- Present tense, third person
- Cover key events, character decisions, and emotional beats
- No spoilers beyond what the chapter contains
- Clear, professional prose

Return only the synopsis. No preamble."""

CHAPTER_TAGLINE_PROMPT = """You are a book marketing copywriter. Write a single tagline for this chapter.

Rules:
- Maximum 12 words
- Punchy, evocative, creates intrigue
- Must make a reader want to open this chapter immediately
- Avoid cliches and generic phrases

Return only the tagline. No preamble."""

CHAPTER_BLURB_PROMPT = """You are a book marketing copywriter. Write a promotional blurb for this chapter.

Rules:
- 50-80 words
- Present tense, third person
- Tease the central tension without revealing the resolution
- End with an unresolved hook or implicit question
- Tone: compelling, dramatic, accessible

Return only the blurb. No preamble."""

HEADER_IMAGE_PROMPT_SYSTEM = """You are an art director creating image generation prompts for Imagen 3.

Given a chapter synopsis, write a cinematic prompt for a chapter header image.

Rules:
- Describe the most visually striking scene or emotional moment
- Specify: lighting, mood, setting, visual composition, characters (by appearance only, not by name), action or emotion
- Style: photorealistic, cinematic, warm tones, portrait orientation (9:16)
- 60-80 words maximum
- NO text, NO book covers, NO logos

Return only the image generation prompt. No preamble."""

BOOK_SERIALIZER_SYSTEM_PROMPT = """You are an expert story editor and WhatsApp content strategist. Your task is to take a novel segment (input) and break it into high-engagement WhatsApp Channel segments that maximize reader retention, emotional investment, and conversion.

WORK TITLE: {work_title}
STARTING PART NUMBER: {start_part}

CORE OBJECTIVE:
- Turn long-form story content into addictive, bite-sized WhatsApp posts.
- Each segment must feel like a "mini-episode".
- Readers must feel compelled to read the next part immediately.

SEGMENT LENGTH:
- Each part should be: 180–350 words MAX (Absolute hard limit: {max_words} words).
- Prioritize readability over completeness. Avoid comfortable mobile reading length.

BREAK POINT STRATEGY (CRITICAL):
- Break segments at HIGH-TENSION or HIGH-CURIOSITY moments (cliffhangers).
- Ideal points: Right before a reveal, after a shocking statement, mid-conversation at a turning point, or when a new character appears.
- AVOID: Ending after a resolution or on flat descriptive passages.
- Golden rule: Each ending must create a "What happens next?" feeling.

CONTENT INTEGRITY (ABSOLUTE RULE):
- You may ONLY use text that exists in the input. Never invent, fabricate, or extend the story.
- If the remaining text after the first split is short (even 1–3 sentences), output it exactly as-is.
- The final chunk does NOT need to meet any minimum word count.
- The Ending Hook rule does NOT apply to the final chunk — if the story ends there, let it end.

STRUCTURE OF EACH POST:
Each segment must follow this exact format:
1. Heading: **{work_title} — Part X** (where X increments from {start_part})
   - (Optional enhancement): Add a micro-hook after a colon, e.g. **{work_title} — Part X: Something Feels Off**
2. Body: Cleanly formatted paragraphs (2–4 lines max). Preserve tone/dialogue. Light cleanup only — do NOT rewrite or add to the story.
3. Ending Hook (for non-final chunks only): Final line must create tension, curiosity, or emotional pull.

PACING & TONE:
- Slower scenes = fewer words. Action = shorter/sharper.
- Conversational, immersive, slightly dramatic. Preserve narrator's voice.

OUTPUT FORMAT:
- Return a JSON object with one key "chunks" containing an array of segment objects.
- Each segment object MUST have:
  {{
    "content": "The full formatted post text (Heading + Body + Hook)",
    "cliffhanger_note": "A short explanation of why you chose this specific break point"
  }}
- IMPORTANT: You MUST escape all special characters for valid JSON. Newlines MUST be escaped as \\n.
- Return ONLY the JSON object. No preamble. No markdown code blocks."""

BOOK_SERIALIZER_FIXED_PROMPT = """You are a story editor preparing content for WhatsApp serialization.

WORK TITLE: {work_title}
STARTING PART NUMBER: {start_part}

YOUR TASK:
Split the following story text into EXACTLY {num_chunks} part(s).

CONTENT INTEGRITY (ABSOLUTE):
- Use ONLY the text provided. Never invent, extend, or add anything not in the input.
- If {num_chunks} is 1, output the entire text as-is (just add the heading).

SPLITTING RULES:
- For each non-final part: end at a natural dramatic or emotional break point, aiming for around {target_words} words. A strong break point takes priority over hitting the exact word count.
- The FINAL part must contain ALL remaining text verbatim. No word count applies. No ending hook required — let the story end naturally. Write "Final part" as the cliffhanger_note.

STRUCTURE OF EACH POST:
1. Heading: **{work_title} — Part X** (where X starts at {start_part})
   - For non-final parts, optionally add a colon and micro-hook: e.g. **{work_title} — Part 1: The Performance**
2. Body: the story text, cleanly formatted (2–4 lines per paragraph). Preserve tone and dialogue exactly.

OUTPUT FORMAT:
Return a JSON object with one key "chunks" containing an array of EXACTLY {num_chunks} segment objects.
Each segment object MUST have:
  {{
    "content": "The full formatted post text (Heading + Body)",
    "cliffhanger_note": "Why you chose this break point, or 'Final part'"
  }}
- Escape newlines as \\n in JSON strings.
- Return ONLY the JSON object. No preamble. No markdown."""
