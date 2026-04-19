"""
Claude-powered natural language parser for the Discord bot.
Turns free-text messages into structured Indaba actions.
"""
import json
import anthropic
from config import ANTHROPIC_API_KEY, AI_MODEL

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You are the Indaba Bot dispatcher. Indaba is a publishing dashboard for a professional writer named Fidel.

Your only job is to parse the user's natural language message and return a JSON object identifying what they want to do.

Available actions and their JSON format:
- Hub overview:        {"action": "hub"}
- List pipeline:       {"action": "pipeline", "book": "", "stage": ""}
- Get one entry:       {"action": "pipeline_get", "entry_id": "..."}
- Move stage:          {"action": "set_stage", "entry_id": "...", "stage": "producing|publishing|promoting"}
- Publish to website:  {"action": "publish", "entry_id": "..."}
- Deploy website:      {"action": "deploy"}
- Deploy status:       {"action": "deploy_status"}
- Work sync:           {"action": "work_sync", "work_id": "LB|OAO|ROTRQ|MOSAS"}
- List works:          {"action": "works"}
- EC2 sender status:   {"action": "status"}
- Add roadmap idea:    {"action": "idea", "text": "...the idea verbatim..."}
- Help:                {"action": "help"}
- Unknown:             {"action": "unknown", "reason": "..."}

Rules:
- Return ONLY valid JSON. No explanation.
- For "idea", capture the full text of the idea exactly as the user wrote it.
- book codes: LB=Love Back, OAO=Outlaws and Outcasts, ROTRQ=Rise of the Rain Queen, MOSAS=Mothers of Suns and Stars
- stage values: producing, publishing, promoting
- If the message is a greeting or small talk, return {"action": "unknown", "reason": "greeting"}
"""


def parse_intent(message: str) -> dict:
    """
    Parse a natural language message and return a structured action dict.
    Falls back to {"action": "unknown"} on any error.
    """
    if not ANTHROPIC_API_KEY:
        return {"action": "unknown", "reason": "ANTHROPIC_API_KEY not set"}

    try:
        client = _get_client()
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        return {"action": "unknown", "reason": str(e)}
