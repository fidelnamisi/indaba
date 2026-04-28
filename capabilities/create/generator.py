"""
AI generation capability — image compositing, proverb post generation,
and WA content production.
"""
import os
import uuid
import random
from datetime import datetime

from utils.json_store import DATA_DIR
from utils.constants import GENERATED_IMAGES_DIR, FONTS_DIR
from services.ai_service import call_ai

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── Proverb post system prompts ───────────────────────────────────────────────

MEANING_SYSTEM = """You write proverb interpretations for a WhatsApp channel called Wisdom & Love Stories.
Audience: African women aged 20-40, mobile-first, emotion-driven.
Tone: warm, reflective, conversational, Hemingway-short sentences.
Perspective: second person (you). Light use of "we". Never "I".
Never: clichés, questions, corporate tone, complex vocabulary, motivational slogans, slang.
Each meaning MUST follow this exact structure in one paragraph:
1. Relatable situation (love, conflict, growth, waiting)
2. Emotional tension (what people feel or struggle with)
3. Insight tied directly to the proverb
4. Grounded closing truth
HARD RULE: Minimum 28 words. Maximum 60 words. One paragraph. 2-4 sentences only.
Return ONLY the meaning text, nothing else."""

PROMPT_SYSTEM = """You write image generation prompts for African proverb social media posts.

MISSION: Generate a prompt that VISUALLY ILLUSTRATES the proverb's core meaning.
The scene must feel emotionally or metaphorically connected to what the proverb says — not generic.

RACIAL REPRESENTATION — MANDATORY, NON-NEGOTIABLE:
- All human subjects must be visibly Black African with dark, rich skin tones
- Always specify: "dark-skinned Black South African" — never leave skin tone ambiguous
- Include authentic visual markers: natural afro hair, braids, locs, or short-cropped natural hair
- South African cultural context: Johannesburg urban setting, South African township, rural KwaZulu-Natal, Cape Winelands, or modern South African suburb
- This channel serves Black South African women aged 20–40. Every image must reflect their world.

SUBJECT VARIETY — rotate across these, never default to "smiling woman":
- Dark-skinned Black South African man (any age 20–70)
- Dark-skinned Black South African woman (any age 20–70)
- Elderly Black South African person (65+)
- Two people together: parent and child, two women, two elders
- A group of three or more Black South African people
- No people at all: an African landscape, animal, meaningful object, or abstract symbolic scene

MOOD — match the proverb, do NOT default to smiling:
- Contemplative, determined, serene, hopeful, solemn, quietly joyful, or dramatic
- A landscape or object can carry mood without any person present

COLOR PALETTE — rotate widely, NEVER default to warm brown tones:
- Rich jewel tones (deep teal, burgundy, forest green, royal blue)
- Cool blue-hour or dusk light with purple and indigo
- Vibrant sunrise orange and pink against a dark sky
- Lush saturated midday greens and yellows
- Stark high-contrast black and white with one accent color
- Warm golden only when the proverb's meaning specifically calls for warmth

COMPOSITION — tight, intentional framing:
- Subject fills most of the frame — NO excessive empty space above the head
- Strong visual anchor at centre or lower third
- Tight portrait from chest up, OR a meaningful wide establishing shot — nothing in between
- Head fills at least 40% of frame height in any portrait shot

CONSTRAINTS:
- 25–40 words
- Photorealistic
- No text, no logos, no watermarks
- Portrait orientation (9:16)
- Return ONLY the image prompt, nothing else"""

# Variety tokens injected into each prompt call to break repetition in bulk generation.
# Each specifies subject, skin tone, and color direction to force diversity.
_VARIETY_TOKENS = [
    "Subject: dark-skinned Black South African man, aged 45–60. Color palette: cool blues and greens.",
    "Subject: no people — African landscape, animal, or symbolic object only. Color: vivid and saturated.",
    "Subject: elderly dark-skinned Black South African woman, age 65+. Color: warm gold and ochre.",
    "Subject: dark-skinned Black South African mother and child together. Color: lush greens.",
    "Subject: dark-skinned Black South African woman, age 30–45, contemplative expression, not smiling. Color: blue-hour purples.",
    "Subject: group of three dark-skinned Black South African people in an outdoor scene. Color: vibrant sunrise.",
    "Subject: close-up of dark-skinned hands, or feet, or a culturally meaningful object — no face. Color: stark contrast.",
    "Subject: young dark-skinned Black South African man, age 20–28, wide establishing shot. Color: deep jewel tones.",
    "Subject: silhouette of a dark-skinned Black South African person against a dramatic African sky.",
    "Subject: an animal — bird, elephant, cattle, lion — in a South African landscape. No people.",
]

CTA_OPTIONS = [
    "React ❤️ if this speaks to you.",
    "React ❤️ if you relate to this.",
    "React ❤️ if you understand this.",
    "React ❤️ if you've felt this.",
    "React ❤️ if this is true for you.",
]


# ── Image compositing ─────────────────────────────────────────────────────────

def composite_proverb_image(photo_url, proverb_text, attribution, meaning, cta):
    """
    Downloads raw photo, composites text overlay, saves to data/generated_images/.
    Returns the local file path.
    Canvas: 1024 × 1536 px portrait (2:3)
    """
    import urllib.request as _url_req

    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is not installed.")

    tmp_path = None
    W, H      = 1024, 1536
    PHOTO_H   = 922
    FADE_H    = 120
    BROWN     = (59, 38, 24)
    OFF_WHITE = (245, 233, 218)
    ATTR_COL  = (234, 217, 197)
    PAD_X     = 102
    TEXT_W    = W - (PAD_X * 2)

    canvas = Image.new('RGB', (W, H), BROWN)

    os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
    if photo_url.startswith('http'):
        tmp_path = os.path.join(GENERATED_IMAGES_DIR, '_tmp_photo.jpg')
        _url_req.urlretrieve(photo_url, tmp_path)
        photo = Image.open(tmp_path).convert('RGB')
    else:
        photo = Image.open(photo_url).convert('RGB')

    scale = W / photo.width
    new_h = int(photo.height * scale)
    photo = photo.resize((W, new_h), Image.LANCZOS)
    photo = photo.crop((0, 0, W, PHOTO_H))
    canvas.paste(photo, (0, 0))

    fade_start = PHOTO_H - FADE_H
    for y in range(FADE_H):
        alpha = y / FADE_H
        for x in range(W):
            r, g, b = canvas.getpixel((x, fade_start + y))
            r = int(r + (BROWN[0] - r) * alpha)
            g = int(g + (BROWN[1] - g) * alpha)
            b = int(b + (BROWN[2] - b) * alpha)
            canvas.putpixel((x, fade_start + y), (r, g, b))

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(0, PHOTO_H), (W, H)], fill=BROWN)

    def font(name, size):
        path = os.path.join(FONTS_DIR, name)
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError) as exc:
            exists = os.path.exists(path)
            sz = os.path.getsize(path) if exists else None
            raise RuntimeError(
                f"Font load failed: name={name} path={path} "
                f"exists={exists} size={sz} fonts_dir={FONTS_DIR} "
                f"dir_exists={os.path.isdir(FONTS_DIR)} underlying={exc}"
            ) from exc

    f_quote   = font('PlayfairDisplay-SemiBoldItalic.ttf', 48)
    f_attr    = font('PlayfairDisplay-Italic.ttf', 28)
    f_label   = font('Inter-Bold.ttf', 26)
    f_meaning = font('Inter-Regular.ttf', 28)
    f_cta     = font('Inter-SemiBold.ttf', 26)

    def draw_wrapped(draw, text, font, colour, x, y, max_w):
        words = text.split()
        lines, line = [], []
        for word in words:
            test = ' '.join(line + [word])
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_w:
                line.append(word)
            else:
                if line: lines.append(' '.join(line))
                line = [word]
        if line: lines.append(' '.join(line))
        for l in lines:
            draw.text((x, y), l, font=font, fill=colour)
            bbox = draw.textbbox((x, y), l, font=font)
            y += (bbox[3] - bbox[1]) + 8
        return y

    def draw_centered(draw, text, font, colour, y, max_w):
        words = text.split()
        lines, line = [], []
        for word in words:
            test = ' '.join(line + [word])
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_w:
                line.append(word)
            else:
                if line: lines.append(' '.join(line))
                line = [word]
        if line: lines.append(' '.join(line))
        for l in lines:
            bbox = draw.textbbox((0, 0), l, font=font)
            lw   = bbox[2] - bbox[0]
            lh   = bbox[3] - bbox[1]
            draw.text(((W - lw) // 2, y), l, font=font, fill=colour)
            y += lh + 8
        return y

    y = PHOTO_H + 40
    y = draw_centered(draw, f'"{proverb_text}"', f_quote, OFF_WHITE, y, TEXT_W)
    y += 12
    y = draw_centered(draw, f'— {attribution}', f_attr, ATTR_COL, y, TEXT_W)
    y += 20

    divider_w = int(W * 0.6)
    divider_x = (W - divider_w) // 2
    draw.line([(divider_x, y), (divider_x + divider_w, y)], fill=(234, 217, 197), width=1)
    y += 24

    draw.text((PAD_X, y), 'Meaning:', font=f_label, fill=OFF_WHITE)
    bbox = draw.textbbox((PAD_X, y), 'Meaning:', font=f_label)
    y += (bbox[3] - bbox[1]) + 10
    y = draw_wrapped(draw, meaning, f_meaning, OFF_WHITE, PAD_X, y, TEXT_W)
    y += 28
    draw.text((PAD_X, y), cta, font=f_cta, fill=OFF_WHITE)

    filename = f'proverb_{uuid.uuid4().hex[:8]}.jpg'
    filepath = os.path.join(GENERATED_IMAGES_DIR, filename)
    canvas.save(filepath, 'JPEG', quality=90)

    if photo_url.startswith('http') and tmp_path and os.path.exists(tmp_path):
        os.remove(tmp_path)

    return filepath


# ── WA post generation ────────────────────────────────────────────────────────

def generate_prompt_only(proverb, variety_hint=None):
    """
    Phase 1: generate meaning + image prompt WITHOUT calling Imagen.
    Returns dict: {meaning, image_prompt}
    """
    meaning_raw = call_ai("wa_post_maker", [
        {"role": "system", "content": MEANING_SYSTEM},
        {"role": "user",   "content":
         f'Proverb: "{proverb["text"]}" (Origin: {proverb.get("origin", "African")})'}
    ])
    meaning = meaning_raw.strip()
    words   = meaning.split()
    if len(words) > 60:
        meaning = ' '.join(words[:60])

    variety_line = f"\nVARIETY INSTRUCTION FOR THIS IMAGE: {variety_hint}" if variety_hint else ""
    img_prompt_raw = call_ai("wa_post_maker", [
        {"role": "system", "content": PROMPT_SYSTEM},
        {"role": "user",   "content":
         f'Proverb: "{proverb["text"]}"\nMeaning: {meaning}{variety_line}'}
    ])
    img_prompt   = img_prompt_raw.strip()
    prompt_words = img_prompt.split()
    if len(prompt_words) > 50:
        img_prompt = ' '.join(prompt_words[:50])

    return {"meaning": meaning, "image_prompt": img_prompt}


def generate_image_and_composite(proverb, meaning, img_prompt):
    """
    Phase 2: call Imagen with an approved/edited prompt and composite the card.
    Mutates proverb in place. Returns result dict.
    """
    import requests as _req
    import base64 as _b64
    from google.oauth2 import service_account as _sa
    from google.auth.transport.requests import Request as _Req

    sa_path = os.environ.get('GOOGLE_SA_KEY', '')
    if not sa_path or not os.path.exists(sa_path):
        raise ValueError("GOOGLE_SA_KEY not set or file not found.")

    _creds = _sa.Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    _creds.refresh(_Req())

    full_prompt = (
        img_prompt
        + ". Photorealistic, cinematic, 9:16 portrait orientation, "
          "tight intentional framing, subject fills the frame, "
          "no text overlay, no logos, no studio backdrop. "
          "CRITICAL: any human subjects must have visibly dark skin — "
          "Black South African representation, rich dark melanin complexion."
    )

    _img_resp = _req.post(
        "https://us-central1-aiplatform.googleapis.com/v1/projects/"
        "gen-lang-client-0717388888/locations/us-central1/"
        "publishers/google/models/imagen-3.0-generate-001:predict",
        headers={"Authorization": f"Bearer {_creds.token}",
                 "Content-Type": "application/json"},
        json={"instances": [{"prompt": full_prompt}],
              "parameters": {"sampleCount": 1, "aspectRatio": "9:16",
                             "personGeneration": "allow_all"}},
        timeout=90,
    )
    if _img_resp.status_code != 200:
        raise ValueError(f"Imagen error {_img_resp.status_code}: {_img_resp.text[:200]}")

    _img_bytes = _b64.b64decode(
        _img_resp.json()["predictions"][0]["bytesBase64Encoded"])

    os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
    tmp_photo = os.path.join(GENERATED_IMAGES_DIR, '_tmp_photo.jpg')
    with open(tmp_photo, 'wb') as _f:
        _f.write(_img_bytes)

    attribution    = proverb.get('origin', 'African') + ' Proverb'
    cta            = random.choice(CTA_OPTIONS)
    composite_path = composite_proverb_image(
        photo_url=tmp_photo,
        proverb_text=proverb['text'],
        attribution=attribution,
        meaning=meaning,
        cta=cta,
    )

    now = datetime.utcnow().isoformat() + "Z"
    proverb.update({
        'used':           True,
        'used_at':        now,
        'meaning':        meaning,
        'image_prompt':   img_prompt,
        'cta':            cta,
        'composite_path': composite_path,
        'queue_status':   "pending",
        'updated_at':     now,
    })

    filename = os.path.basename(composite_path)
    return {
        "proverb_id":     proverb['id'],
        "proverb_text":   proverb['text'],
        "attribution":    attribution,
        "meaning":        meaning,
        "cta":            cta,
        "image_prompt":   img_prompt,
        "composite_url":  f"/data/images/{filename}",
        "composite_path": composite_path,
    }


def generate_single_post(proverb, proverbs_data, variety_hint=None):
    """
    Generate meaning, image prompt, Imagen 3 photo, and composite for one proverb.
    Mutates proverb dict in place. Returns result dict.
    Raises Exception on failure.

    variety_hint: optional string injected into the prompt user message to drive
                  subject/color/composition variety across bulk calls.
    """
    import requests as _req
    import base64 as _b64
    from google.oauth2 import service_account as _sa
    from google.auth.transport.requests import Request as _Req

    # Step 1: Generate meaning
    meaning_raw = call_ai("wa_post_maker", [
        {"role": "system", "content": MEANING_SYSTEM},
        {"role": "user",   "content":
         f'Proverb: "{proverb["text"]}" (Origin: {proverb.get("origin", "African")})'}
    ])
    meaning = meaning_raw.strip()
    words   = meaning.split()
    if len(words) > 60:
        meaning = ' '.join(words[:60])

    # Step 2: Generate image prompt — inject variety hint to prevent repetition
    variety_line = f"\nVARIETY INSTRUCTION FOR THIS IMAGE: {variety_hint}" if variety_hint else ""
    img_prompt_raw = call_ai("wa_post_maker", [
        {"role": "system", "content": PROMPT_SYSTEM},
        {"role": "user",   "content":
         f'Proverb: "{proverb["text"]}"\nMeaning: {meaning}{variety_line}'}
    ])
    img_prompt   = img_prompt_raw.strip()
    prompt_words = img_prompt.split()
    if len(prompt_words) > 50:
        img_prompt = ' '.join(prompt_words[:50])

    # Step 3: Generate image via Google Vertex Imagen 3
    sa_path = os.environ.get('GOOGLE_SA_KEY', '')
    if not sa_path or not os.path.exists(sa_path):
        raise ValueError("GOOGLE_SA_KEY not set or file not found.")

    _creds = _sa.Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    _creds.refresh(_Req())

    # Let the AI-generated prompt lead. Append only technical requirements
    # and a hard racial-representation constraint that Imagen cannot override.
    full_prompt = (
        img_prompt
        + ". Photorealistic, cinematic, 9:16 portrait orientation, "
          "tight intentional framing, subject fills the frame, "
          "no text overlay, no logos, no studio backdrop. "
          "CRITICAL: any human subjects must have visibly dark skin — "
          "Black South African representation, rich dark melanin complexion."
    )

    _img_resp = _req.post(
        "https://us-central1-aiplatform.googleapis.com/v1/projects/"
        "gen-lang-client-0717388888/locations/us-central1/"
        "publishers/google/models/imagen-3.0-generate-001:predict",
        headers={"Authorization": f"Bearer {_creds.token}",
                 "Content-Type": "application/json"},
        json={"instances": [{"prompt": full_prompt}],
              "parameters": {"sampleCount": 1, "aspectRatio": "9:16",
                             "personGeneration": "allow_all"}},
        timeout=90,
    )

    if _img_resp.status_code != 200:
        raise ValueError(f"Imagen error {_img_resp.status_code}: {_img_resp.text[:200]}")

    _img_bytes = _b64.b64decode(
        _img_resp.json()["predictions"][0]["bytesBase64Encoded"])

    os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
    tmp_photo = os.path.join(GENERATED_IMAGES_DIR, '_tmp_photo.jpg')
    with open(tmp_photo, 'wb') as _f:
        _f.write(_img_bytes)

    # Step 4: Composite
    attribution    = proverb.get('origin', 'African') + ' Proverb'
    cta            = random.choice(CTA_OPTIONS)
    composite_path = composite_proverb_image(
        photo_url=tmp_photo,
        proverb_text=proverb['text'],
        attribution=attribution,
        meaning=meaning,
        cta=cta,
    )

    # Step 5: Update proverb in place
    now = datetime.utcnow().isoformat() + "Z"
    proverb.update({
        'used':           True,
        'used_at':        now,
        'meaning':        meaning,
        'image_prompt':   img_prompt,
        'cta':            cta,
        'composite_path': composite_path,
        'queue_status':   "pending",
        'updated_at':     now,
    })

    filename = os.path.basename(composite_path)
    return {
        "proverb_id":     proverb['id'],
        "proverb_text":   proverb['text'],
        "attribution":    attribution,
        "meaning":        meaning,
        "cta":            cta,
        "image_prompt":   img_prompt,
        "composite_url":  f"/data/images/{filename}",
        "composite_path": composite_path,
    }
