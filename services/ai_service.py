import json
import os
from openai import OpenAI
from utils.json_store import read_json

# Configuration for AI Providers
PROMO_SETTINGS_FILE = 'promo_settings.json'

DEFAULT_AI_CONFIG = {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key_env": "DEEPSEEK_API_KEY"
}

def call_ai(provider_key, messages, max_tokens=1000, **kwargs):
    """Refactored logic for calling AI providers based on JSON config."""
    from utils.json_store import DATA_DIR
    path = os.path.join(DATA_DIR, PROMO_SETTINGS_FILE)
    
    config = DEFAULT_AI_CONFIG
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                settings = json.load(f)
                config = settings.get("ai_providers", {}).get(provider_key, DEFAULT_AI_CONFIG)
        except:
             pass

    api_key_env = config.get("api_key_env", "DEEPSEEK_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    
    if not api_key:
        # Fallback to general DEEPSEEK_API_KEY or OPENAI_API_KEY
        api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(f"AI api key not found for {api_key_env}")

    base_url = "https://api.deepseek.com" if config.get("provider") == "deepseek" else None
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=config.get("model", "deepseek-chat"),
        messages=messages,
        max_tokens=max_tokens,
        **kwargs
    )
    return resp.choices[0].message.content

class AIService:
    @staticmethod
    def generate_synopsis(chapter_title, prose):
        prompt = f"Write a professional 2-sentence synopsis for the chapter '{chapter_title}'. Base it on this prose:\n\n{prose[:2000]}"
        return call_ai("synopsis_maker", [{"role": "user", "content": prompt}])

    @staticmethod
    def generate_tagline(chapter_title, prose):
        prompt = f"Write a single punchy social media tagline (hook) for this chapter '{chapter_title}'. Prose:\n\n{prose[:1500]}"
        return call_ai("tagline_maker", [{"role": "user", "content": prompt}])

    @staticmethod
    def extract_excerpt(chapter_title, prose):
        prompt = f"Select a high-impact, emotionally resonant 50-word excerpt from this chapter segment. Return ONLY the excerpt text.\n\n{prose[:3000]}"
        return call_ai("excerpt_maker", [{"role": "user", "content": prompt}])

    @staticmethod
    def generate_blurb(chapter_title, prose):
        prompt = f"Write a 50-word promotional blurb for this chapter '{chapter_title}'. Make it sound like a back-cover blurb. Prose:\n\n{prose[:2000]}"
        return call_ai("blurb_maker", [{"role": "user", "content": prompt}])
