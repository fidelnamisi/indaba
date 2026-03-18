#!/usr/bin/env python3
"""
Regenerate tagline fields for all chapters using the new prompt.
"""

import json
import os
import sys
import time
from typing import List, Dict, Any
from openai import OpenAI

# Configuration
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
API_KEY_ENV_VAR = "DEEPSEEK_API_KEY"

INPUT_FILE = "/Users/fidelnamisi/Indaba/data/generated_assets.json"
OUTPUT_FILE = INPUT_FILE  # overwrite same file

def load_assets() -> List[Dict[str, Any]]:
    """Load existing assets from JSON file."""
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        sys.exit(1)
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_assets(assets: List[Dict[str, Any]]) -> None:
    """Save assets to JSON file."""
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(assets, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(assets)} chapters to {OUTPUT_FILE}")

def call_deepseek(client: OpenAI, prompt: str, max_retries: int = 3) -> str:
    """Call DeepSeek API with given prompt and return response text."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"API call attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2)
    return ""

def generate_tagline(client: OpenAI, synopsis: str) -> str:
    """Generate a new tagline using the provided synopsis as chapter text."""
    prompt = f"""Write a single tagline for this chapter.

Do NOT use a fixed sentence formula. Instead, read the chapter and decide which of these six angles produces the sharpest, most arresting line for this specific material:

1. THEME — What does this chapter mean? (e.g. "Prophecy chooses its heroes. Destiny tests them.")
2. CONFLICT — What is clashing, and why does it matter? (e.g. "The prophecy has begun — and the wrong prince heard it.")
3. STAKES — What can be lost, and how much? (e.g. "A kingdom waits for its saviour. It may have chosen its ruin.")
4. MYSTERY — What isn't understood, or what is being hidden? (e.g. "Some prophecies are meant to be broken.")
5. IRONY — Where do expectations flip? (e.g. "The chosen one was never supposed to survive.")
6. CHARACTER DILEMMA — What impossible choice defines someone in this chapter? (e.g. "To save the empire, she must become what she hates.")

Rules:
- Pick whichever angle produces the most powerful line for THIS chapter. Don't rotate mechanically.
- The sentence structure should fit the content — vary it across chapters. Avoid starting every tagline the same way.
- Maximum 1–2 sentences. Shorter is almost always better.
- No exposition. No setup. Pure compression — one sharp idea with contrast, irony, or escalation baked in.
- Genre: epic African fantasy. Tone: mythic, cinematic, dangerous.
- Output only the tagline. No headers, no explanation, no angle label.

{synopsis}"""
    return call_deepseek(client, prompt)

def main():
    api_key = os.getenv(API_KEY_ENV_VAR)
    if not api_key:
        print(f"Error: Environment variable {API_KEY_ENV_VAR} not set.")
        sys.exit(1)
    
    client = OpenAI(
        base_url=DEEPSEEK_API_BASE,
        api_key=api_key
    )
    
    assets = load_assets()
    print(f"Loaded {len(assets)} chapters.")
    
    updated = 0
    for idx, entry in enumerate(assets):
        book = entry["book"]
        chapter = entry["chapter"]
        chapter_num = entry["chapter_number"]
        synopsis = entry["assets"]["synopsis"]
        
        print(f"[{idx+1}/{len(assets)}] {book} Chapter {chapter_num}: {chapter}")
        
        # Generate new tagline
        try:
            new_tagline = generate_tagline(client, synopsis)
            # Ensure we have a non-empty string
            if not new_tagline or new_tagline.isspace():
                print(f"  Warning: Empty tagline generated, keeping old.")
                continue
            # Update entry
            entry["assets"]["tagline"] = new_tagline
            updated += 1
            print(f"  New tagline: {new_tagline}")
        except Exception as e:
            print(f"  Error generating tagline: {e}")
            # Continue with next chapter; maybe keep old tagline
            continue
        
        # Save after each chapter (overwrite file)
        save_assets(assets)
        
        # Delay to avoid rate limiting
        time.sleep(0.5)
    
    print(f"\nDone. Updated {updated} chapters.")
    
    # Print summary
    print("\n--- Summary ---")
    for entry in assets:
        print(f"{entry['book']} Chapter {entry['chapter_number']}: {entry['chapter']}")
        print(f"  {entry['assets']['tagline']}")
        print()

if __name__ == "__main__":
    main()