#!/usr/bin/env python3
"""
Generate chapter assets for three novels using DeepSeek API.
"""

import json
import os
import re
import subprocess
import time
import sys
from typing import List, Dict, Any, Optional
from openai import OpenAI

# Configuration
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
API_KEY_ENV_VAR = "DEEPSEEK_API_KEY"

# Novel definitions
NOVELS = [
    {
        "code": "ROTRQ",
        "title": "Rise of the Rain Queen",
        "path": "/Users/fidelnamisi/Indaba/publishing/novels/ROTRQ/rise-of-the-rain-queen-fullMS.docx",
        "chapters": [
            "The Drum Thief",
            "Fractured",
            "Captured",
            "Blood and Betrayal",
            "The Debt Is Settled",
            "The Sound That Woke The Thunder",
            "No More Blood",
            "The Final Order"
        ]
    },
    {
        "code": "OAO",
        "title": "Outlaws and Outcasts",
        "path": "/Users/fidelnamisi/Indaba/publishing/novels/OAO/outlaws-and-outcasts-fullMS.docx",
        "chapters": [
            "The Oracle, the Prophecy and the Traitor",
            "Spears And Fangs",
            "The Wild Dog",
            "Children of the Drum",
            "Death Of A King",
            "The Two Riders",
            "Ghosts in a Tavern",
            "The Shadow of the Drum",
            "The Mountains of Mwari"
        ]
    },
    {
        "code": "MOSAS",
        "title": "Man of Stone and Shadow",
        "path": "/Users/fidelnamisi/Indaba/publishing/novels/MOSAS/man-of-stone-and-shadow-fullMS.docx",
        "chapters": None  # chapters detected by pattern ^Chapter \d+$
    }
]

OUTPUT_FILE = "/Users/fidelnamisi/Indaba/data/generated_assets.json"

def extract_plain_text(docx_path: str) -> str:
    """Convert DOCX to plain text using pandoc."""
    try:
        result = subprocess.run(
            ["pandoc", "-t", "plain", docx_path],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error converting {docx_path}: {e}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)

def split_chapters(text: str, chapters: Optional[List[str]], code: str) -> List[Dict[str, Any]]:
    r"""
    Split plain text into chapters.
    For ROTRQ and OAO, use explicit chapter headings.
    For MOSAS, detect lines matching '^Chapter \d+$'.
    Returns list of dicts with 'title' and 'content'.
    """
    if chapters is not None:
        # Use explicit chapter titles
        pattern = "|".join(re.escape(ch) for ch in chapters)
        # Create regex that matches any of the chapter titles as a whole line
        regex = r'^(?P<title>' + pattern + r')\s*$'
        parts = re.split(regex, text, flags=re.MULTILINE)
        # The first part is content before first chapter heading (ignore)
        # Subsequent parts alternate between title and content
        result = []
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                title = parts[i].strip()
                content = parts[i + 1].strip()
                result.append({"title": title, "content": content})
        # If splitting didn't produce expected number, fallback to simple split
        if len(result) != len(chapters):
            print(f"Warning: Chapter splitting for {code} produced {len(result)} chapters, expected {len(chapters)}")
            # fallback: assign chapters sequentially (simplistic)
            # This is a placeholder; better handling may be needed
            result = []
            lines = text.split('\n')
            # This is a simplistic fallback; we'll implement a more robust method later
            # For now, we'll just return empty list to avoid errors
            pass
        return result
    else:
        # MOSAS: split by lines matching 'Chapter \d+'
        lines = text.split('\n')
        chapters_data = []
        current_title = None
        current_content = []
        for line in lines:
            if re.match(r'^Chapter \d+$', line.strip()):
                if current_title is not None:
                    chapters_data.append({
                        "title": current_title,
                        "content": '\n'.join(current_content).strip()
                    })
                current_title = line.strip()
                current_content = []
            else:
                current_content.append(line)
        if current_title is not None:
            chapters_data.append({
                "title": current_title,
                "content": '\n'.join(current_content).strip()
            })
        return chapters_data

def load_existing_assets() -> List[Dict[str, Any]]:
    """Load previously generated assets from JSON file."""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read {OUTPUT_FILE}: {e}")
            return []
    else:
        return []

def save_assets(assets: List[Dict[str, Any]]) -> None:
    """Save assets to JSON file."""
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
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
                max_tokens=2000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"API call attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2)
    return ""

def generate_synopsis(client: OpenAI, chapter_text: str) -> str:
    prompt = f"""Give me a minimum 500 words and maximum 600 words long synopsis of the following, written in the present tense. Double check your output to ensure you hit the word count I've asked for. Repeat until you hit the desired word count. Do not introduce the conclusion with words like 'the story concludes with' or 'the story ends with'. Just write it out straight without wasting words on such useless fineries. Also, do not include any titles or headings in your final output. Avoid dramatic or artistic flair. All I need is a functional summary for a working writer. It's not for an audience member, but rather simply a tool. Do not add any interpretation or analysis of meaning or stakes or characters or motivations. Just stick to the facts.

{chapter_text}"""
    return call_deepseek(client, prompt)

def generate_blurb(client: OpenAI, chapter_text: str) -> str:
    prompt = f"""Write a 4-sentence blurb for this chapter using this exact formula:
- Sentence 1: When [inciting event], [protagonist] must [goal/action]
- Sentence 2: But [major complication or antagonist] stands in the way
- Sentence 3: As [situation escalates], the stakes rise because [what can be lost]
- Sentence 4: If [protagonist] can't [solve the problem], [serious consequence] will happen

Genre: epic African fantasy. Tone: atmospheric, mythic, cinematic. Target: adult commercial fiction readers. Use short sentences, strong verbs, no exposition. End with a hook that forces the reader to turn the page. Output only the 4-sentence blurb — no headers, no explanation.

{chapter_text}"""
    return call_deepseek(client, prompt)

def generate_tagline(client: OpenAI, chapter_text: str) -> str:
    prompt = f"""Write a single-sentence Hollywood logline for this chapter using this format:
When [inciting event], a [protagonist descriptor] must [goal], but [major obstacle], or else [stakes].

Output only the single sentence. No headers, no explanation.

{chapter_text}"""
    return call_deepseek(client, prompt)

def generate_image_prompt(client: OpenAI, chapter_text: str) -> str:
    prompt = f"""Write an image generation prompt for a 1200x400px chapter banner for this chapter.

Rules:
- Art style: High-end epic fantasy book illustration, painterly cinematic digital art, professional fantasy concept art, hyper-detailed environments, realistic anatomy, volumetric lighting, cinematic depth-of-field
- STRICTLY AVOID: anime, cartoon, comic book, photorealistic photography, sci-fi neon
- Brand palette: use #0A1F3C (deep shadows/skies), #E1B15A (sunlight/gold/highlights), #D9772B (firelight/ember accents), #1E5E4E (mist/magical undertones), plus natural tones: earth browns, clay reds, volcanic stone greys, parchment beige
- No neon, no oversaturation — rich cinematic atmospheric tones only
- Composition: rule of thirds, strong foreground/midground/background layering, clear focal point
- The upper third OR right third should be darker/less busy — safe for text overlay
- Always end with: "Ultra high detail. Cinematic lighting. Professional fantasy concept art. Clean rendering at 1200x400px."
- Setting: ancient southeastern Africa
- Base the visual concept on the key dramatic moment of this chapter

Output only the image prompt text. No headers, no explanation.

{chapter_text}"""
    return call_deepseek(client, prompt)

def main():
    # Check API key
    api_key = os.getenv(API_KEY_ENV_VAR)
    if not api_key:
        print(f"Error: Environment variable {API_KEY_ENV_VAR} not set.")
        sys.exit(1)
    
    client = OpenAI(
        base_url=DEEPSEEK_API_BASE,
        api_key=api_key
    )
    
    # Load existing assets
    existing = load_existing_assets()
    processed = {(item["book"], item["chapter"]): item for item in existing}
    
    all_assets = existing.copy()
    
    for novel in NOVELS:
        code = novel["code"]
        path = novel["path"]
        chapters = novel["chapters"]
        print(f"\n--- Processing {code}: {novel['title']} ---")
        
        # Extract plain text
        print(f"Extracting text from {path}...")
        text = extract_plain_text(path)
        
        # Split into chapters
        print("Splitting into chapters...")
        chapter_data = split_chapters(text, chapters, code)
        print(f"Found {len(chapter_data)} chapters.")
        
        # Ensure chapter count matches expectation
        if chapters is not None and len(chapter_data) != len(chapters):
            print(f"Warning: Expected {len(chapters)} chapters but got {len(chapter_data)}.")
            # We'll still process what we have
        
        for idx, chap in enumerate(chapter_data):
            title = chap["title"]
            chapter_num = idx + 1
            content = chap["content"]
            
            # Skip if already processed
            if (code, title) in processed:
                print(f"  Chapter {chapter_num}: {title} already processed, skipping.")
                continue
            
            print(f"  Chapter {chapter_num}: {title} (length: {len(content)} chars)")
            
            # Generate assets
            print("    Generating synopsis...")
            synopsis = generate_synopsis(client, content)
            time.sleep(1)
            
            print("    Generating blurb...")
            blurb = generate_blurb(client, content)
            time.sleep(1)
            
            print("    Generating tagline...")
            tagline = generate_tagline(client, content)
            time.sleep(1)
            
            print("    Generating image prompt...")
            image_prompt = generate_image_prompt(client, content)
            time.sleep(1)
            
            # Create asset entry
            entry = {
                "book": code,
                "chapter": title,
                "chapter_number": chapter_num,
                "assets": {
                    "synopsis": synopsis,
                    "blurb": blurb,
                    "tagline": tagline,
                    "image_prompt": image_prompt
                }
            }
            
            all_assets.append(entry)
            # Save after each chapter
            save_assets(all_assets)
            print(f"    Saved assets for {title}.")
    
    print(f"\nDone! Total chapters processed: {len(all_assets)}")

if __name__ == "__main__":
    main()