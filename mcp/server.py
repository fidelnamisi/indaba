#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp[cli]>=1.0.0", "httpx>=0.27.0"]
# ///
"""
Indaba MCP Server — gives Claude native programmatic access to all Indaba operations.

Run as a subprocess by Claude Code (stdio transport).
All tools call the Indaba Flask API at http://localhost:5050.

No manual pip install needed — uv handles deps automatically.
Register in Indaba/.mcp.json (already done) then restart Claude.
"""

import json
import sys
import httpx
from mcp.server.fastmcp import FastMCP

INDABA_BASE = "http://localhost:5050"
TIMEOUT     = 60.0  # seconds

mcp = FastMCP("indaba")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict:
    """GET from Indaba API. Returns parsed JSON or raises."""
    url = f"{INDABA_BASE}{path}"
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(url, params=params)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict | None = None) -> dict:
    """POST to Indaba API. Returns parsed JSON or raises."""
    url = f"{INDABA_BASE}{path}"
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(url, json=body or {})
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        # Include the response body in the error for debugging
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:500]
        raise RuntimeError(f"HTTP {r.status_code}: {detail}") from e
    return r.json()


def _put(path: str, body: dict) -> dict:
    url = f"{INDABA_BASE}{path}"
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.put(url, json=body)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:500]
        raise RuntimeError(f"HTTP {r.status_code}: {detail}") from e
    return r.json()


def _delete(path: str) -> dict:
    url = f"{INDABA_BASE}{path}"
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.delete(url)
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Content Pipeline — CRUD
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def pipeline_list(book: str = "", stage: str = "") -> str:
    """
    List all content pipeline entries.

    Args:
        book:  Optional book/series code to filter by (e.g. "LB" for Love Back).
        stage: Optional workflow stage to filter by: producing | publishing | promoting.

    Returns JSON array of pipeline entries.
    """
    entries = _get("/api/content-pipeline")
    if book:
        entries = [e for e in entries if e.get("book") == book]
    if stage:
        entries = [e for e in entries if e.get("workflow_stage") == stage]
    return json.dumps(entries, indent=2)


@mcp.tool()
def pipeline_get(entry_id: str) -> str:
    """
    Get a single pipeline entry by its ID.

    Args:
        entry_id: The pipeline entry ID (e.g. "love-back-ch2-pipeline").

    Returns full JSON of the entry.
    """
    return json.dumps(_get(f"/api/content-pipeline/{entry_id}"), indent=2)


@mcp.tool()
def pipeline_update(entry_id: str, updates: str) -> str:
    """
    Update any fields on a pipeline entry.

    Args:
        entry_id: The pipeline entry ID.
        updates:  JSON string of fields to update. E.g.:
                  '{"assets": {"blurb": "...", "tagline": "..."}}'
                  '{"notes": "Needs revision"}'
                  You can update nested dicts like assets, producing_status, publishing_status.

    Returns the updated entry as JSON.
    """
    data = json.loads(updates)
    return json.dumps(_put(f"/api/content-pipeline/{entry_id}", data), indent=2)


@mcp.tool()
def pipeline_add(
    chapter_title: str,
    book: str,
    chapter_number: int = 0,
    work_type: str = "Book",
    prose: str = "",
    blurb: str = "",
    tagline: str = "",
) -> str:
    """
    Add a new entry to the content pipeline.

    Args:
        chapter_title:  Title of the chapter / module.
        book:           Series/book code (e.g. "LB").
        chapter_number: Chapter number. If 0, auto-assigned.
        work_type:      Work type: Book | Podcast | Subscription | etc. Default: Book.
        prose:          Full prose text for the chapter (optional).
        blurb:          Marketing blurb (optional).
        tagline:        One-line tagline (optional).

    Returns the created entry as JSON.
    """
    body: dict = {
        "chapter":      chapter_title,
        "book":         book,
        "work_type":    work_type,
        "workflow_stage": "publishing" if (prose and blurb and tagline) else "producing",
    }
    if chapter_number:
        body["chapter_number"] = chapter_number

    assets: dict = {}
    if prose:
        assets["prose"] = prose
    if blurb:
        assets["blurb"] = blurb
    if tagline:
        assets["tagline"] = tagline
    if assets:
        body["assets"] = assets

    if prose:
        body.setdefault("producing_status", {})["essential_asset"] = "done"

    return json.dumps(_post("/api/content-pipeline", body), indent=2)


@mcp.tool()
def pipeline_delete(entry_id: str) -> str:
    """
    Delete a pipeline entry permanently.

    Args:
        entry_id: The pipeline entry ID.
    """
    return json.dumps(_delete(f"/api/content-pipeline/{entry_id}"), indent=2)


@mcp.tool()
def pipeline_set_stage(entry_id: str, stage: str) -> str:
    """
    Move a pipeline entry to a different workflow stage.

    Args:
        entry_id: The pipeline entry ID.
        stage:    One of: producing | publishing | promoting.

    Returns the updated entry.
    """
    if stage not in ("producing", "publishing", "promoting"):
        return json.dumps({"error": "stage must be: producing | publishing | promoting"})
    return json.dumps(_put(f"/api/content-pipeline/{entry_id}/workflow-stage", {"stage": stage}), indent=2)


@mcp.tool()
def pipeline_update_producing_status(
    entry_id: str,
    essential_asset: str = "",
    supporting_assets: str = "",
) -> str:
    """
    Update the producing_status of a pipeline entry.

    Args:
        entry_id:          The pipeline entry ID.
        essential_asset:   "done" or "missing".
        supporting_assets: JSON string of supporting asset status updates.
                           E.g. '{"blurb": "done", "tagline": "done", "header_image": "missing"}'

    Returns the updated entry.
    """
    body: dict = {}
    if essential_asset:
        body["essential_asset"] = essential_asset
    if supporting_assets:
        body["supporting_assets"] = json.loads(supporting_assets)
    return json.dumps(_put(f"/api/content-pipeline/{entry_id}/producing-status", body), indent=2)


@mcp.tool()
def pipeline_update_publishing_status(entry_id: str, updates: str) -> str:
    """
    Update the publishing_status of a pipeline entry (per-platform status).

    Args:
        entry_id: The pipeline entry ID.
        updates:  JSON string of platform status updates.
                  E.g. '{"website": "live", "patreon": "published", "wa_channel": "sent"}'
                  Valid values: not_started | live | published | sent | failed.

    Returns the updated entry.
    """
    data = json.loads(updates)
    return json.dumps(_put(f"/api/content-pipeline/{entry_id}/publishing-status", data), indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Asset Generation
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def generate_asset(entry_id: str, asset_type: str) -> str:
    """
    Generate a single AI asset for a pipeline entry using Indaba's configured prompts.

    This uses the prose already stored in the entry. Run AFTER prose is saved.

    Args:
        entry_id:   The pipeline entry ID.
        asset_type: One of: synopsis | blurb | tagline | image_prompt
                    (synopsis first — blurb/tagline/image_prompt use synopsis as input)

    Returns: {"ok": true, "result": "<generated text>", "asset_type": "..."}

    IMPORTANT: After generation, call pipeline_update to save the result to the entry's assets.
    The return value contains the generated text — you must explicitly save it.
    """
    body = {"asset_type": asset_type}
    result = _post(f"/api/modules/{entry_id}/generate-asset", body)
    return json.dumps(result, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Website Publishing
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def website_publish(entry_id: str) -> str:
    """
    Publish a single pipeline entry as a static HTML page on realmsandroads.com.

    Prerequisites — the entry must have:
      - blurb (non-empty)
      - tagline (non-empty)
      - prose (at least 100 characters)
      - book must be a known series code (e.g. "LB")
      - chapter_number must be a positive integer

    This writes the HTML to the local website folder. Call website_deploy afterwards
    to push it live to Amplify.

    Args:
        entry_id: The pipeline entry ID.

    Returns: {"ok": true, "chapter_url": "...", "chapter_slug": "...", ...}
    """
    return json.dumps(_post("/api/website/publish", {"entry_id": entry_id}), indent=2)


@mcp.tool()
def website_publish_batch(entry_ids: str) -> str:
    """
    Publish multiple pipeline entries to the website in one go.

    Args:
        entry_ids: JSON array string of entry IDs.
                   E.g. '["lb-ch3", "lb-ch4", "lb-ch5"]'

    Returns: {"results": [{"entry_id": "...", "ok": true/false, "error": null}, ...]}
    """
    ids = json.loads(entry_ids)
    return json.dumps(_post("/api/website/publish-batch", {"entry_ids": ids}), indent=2)


@mcp.tool()
def website_deploy() -> str:
    """
    Deploy the local website to AWS Amplify (realmsandroads.com goes live).

    This zips the public/ folder, uploads to Amplify, and waits for the
    deployment to succeed. Takes ~2 minutes. Check website_deploy_status to poll.

    Returns: {"ok": true, "deploying": true} then poll website_deploy_status.
    """
    return json.dumps(_post("/api/website/deploy"), indent=2)


@mcp.tool()
def website_deploy_status() -> str:
    """
    Check the current website deployment status.

    Returns: {"state": "idle|deploying|deployed|failed", "started_at": "...", "finished_at": "...", "error": null}
    """
    return json.dumps(_get("/api/website/deploy-status"), indent=2)


@mcp.tool()
def website_work_sync(work_id: str) -> str:
    """
    Compare Indaba's pipeline with what's actually live on the website for a given work.

    Useful for seeing which chapters are published, which are stale, and which
    exist on the website but aren't in Indaba.

    Args:
        work_id: Series/book code (e.g. "LB").

    Returns: {"ok": true, "chapters": [...], "series": "Love Back"}
    """
    return json.dumps(_get(f"/api/website/work-sync/{work_id}"), indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Works / Catalog
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def works_list() -> str:
    """
    List all works in the catalog with their pipeline module counts and chapter list.

    Returns JSON with works array, each including module_count and modules list.
    """
    return json.dumps(_get("/api/catalog-works"), indent=2)


@mcp.tool()
def works_create(
    title: str,
    series_code: str,
    url_slug: str,
    genre: str = "Fantasy",
    author: str = "Fidel Namisi",
    chapters_text: str = "",
) -> str:
    """
    Create a new Book work in the catalog.

    This also registers the series in series_config.json so the website publisher
    can find it. Optionally bulk-imports chapters from markdown text.

    Args:
        title:         Full title of the work (e.g. "Love Back").
        series_code:   Short uppercase code (e.g. "LB"). Must be unique.
        url_slug:      URL-friendly slug (e.g. "love-back"). Used in chapter URLs.
        genre:         Genre string (e.g. "Fantasy", "Romance").
        author:        Author name. Default: Fidel Namisi.
        chapters_text: Optional: bulk import chapters as markdown.
                       Format: ## Chapter Title\\nChapter prose...\\n\\n## Next Chapter\\n...
                       Each ## heading becomes a new pipeline entry.

    Returns: {"work": {...}, "chapters_imported": N}
    """
    body = {
        "title":        title,
        "work_type":    "Book",
        "series_code":  series_code,
        "url_slug":     url_slug,
        "genre":        genre,
        "author":       author,
    }
    if chapters_text:
        body["chapters_text"] = chapters_text
    return json.dumps(_post("/api/catalog-works", body), indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Flash Fiction
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def flash_fiction_generate(
    genre: str,
    trope: str,
    twist: str,
    setting_place: str,
    setting_era: str,
    setting_atmosphere: str,
    word_count: int = 500,
    pov: str = "third-person limited",
    character: str = "",
    emotion: str = "",
    constraint: str = "",
) -> str:
    """
    Generate a flash fiction story using Indaba's built-in AI pipeline.

    This calls Anthropic claude-sonnet directly via Indaba's AI service.
    The output is a complete, polished piece of flash fiction with a self-score.

    Args:
        genre:              E.g. "African fantasy", "magical realism", "thriller".
        trope:              Core story trope. E.g. "reluctant hero", "forbidden love".
        twist:              The narrative twist. E.g. "the mentor is the villain".
        setting_place:      Geographic/physical location. E.g. "the Mara savanna".
        setting_era:        Time period. E.g. "pre-colonial Africa", "near future".
        setting_atmosphere: Tone/mood. E.g. "eerie and still", "electric with tension".
        word_count:         Target word count. Default: 500.
        pov:                Point of view. Default: "third-person limited".
        character:          Optional character name or brief description.
        emotion:            Optional dominant emotion to convey.
        constraint:         Optional formal constraint (e.g. "no dialogue", "one sentence paragraphs").

    Returns the generated story text plus self-score as JSON.
    """
    body = {
        "genre":              genre,
        "trope":              trope,
        "twist":              twist,
        "setting_place":      setting_place,
        "setting_era":        setting_era,
        "setting_atmosphere": setting_atmosphere,
        "word_count":         word_count,
        "pov":                pov,
    }
    if character:
        body["character"] = character
    if emotion:
        body["emotion"] = emotion
    if constraint:
        body["constraint"] = constraint

    return json.dumps(_post("/api/flash-fiction/generate", body), indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 6. WA Channel — Queue Only (never direct publish)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def queue_wa_message(
    module_id: str,
    recipient: str,
    message_text: str,
    media_url: str = "",
) -> str:
    """
    Queue a WhatsApp message for a pipeline module.

    IMPORTANT: This NEVER sends directly. It queues to the EC2 outbox for scheduled
    delivery by the Indaba sender process. Always use this — never direct-send.

    Args:
        module_id:    The pipeline entry ID this message is associated with.
        recipient:    "vip_group" or "channel".
        message_text: The WA message body text.
        media_url:    Optional URL for media attachment.

    Returns: {"ok": true, "queued_at": "...", "message_id": "..."}
    """
    if recipient not in ("vip_group", "channel"):
        return json.dumps({"error": "recipient must be 'vip_group' or 'channel'"})

    body: dict = {
        "recipient":    recipient,
        "message_text": message_text,
    }
    if media_url:
        body["media_url"] = media_url

    return json.dumps(_post(f"/api/publishing/modules/{module_id}/queue_wa", body), indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Promo Broadcast Posts
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def promo_broadcast_generate(proverb_id: str) -> str:
    """
    Generate a broadcast post (with AI-written caption and optional image) for a proverb.

    This uses Indaba's promo pipeline. After generation, call promo_broadcast_queue
    to queue it for delivery.

    Args:
        proverb_id: ID of the proverb entry in promo_proverbs.json.

    Returns: The generated broadcast post object as JSON.
    """
    return json.dumps(_post("/api/promo/broadcast_post/generate", {"proverb_id": proverb_id}), indent=2)


@mcp.tool()
def promo_broadcast_queue(proverb_id: str, channel: str = "channel") -> str:
    """
    Queue an approved broadcast post for delivery via the EC2 outbox.

    IMPORTANT: Always queues to EC2 outbox — never direct-sends. The Indaba
    sender process picks it up and delivers at the scheduled time.

    Args:
        proverb_id: ID of the proverb/broadcast post.
        channel:    Delivery channel. Default: "channel".

    Returns: {"ok": true, "queued": true}
    """
    return json.dumps(_post(f"/api/promo/broadcast_post/{proverb_id}/queue", {"channel": channel}), indent=2)


@mcp.tool()
def promo_broadcast_list() -> str:
    """
    List all proverbs available for broadcast post generation.

    Returns the proverbs from promo_proverbs.json as JSON.
    """
    # The broadcast post endpoint doesn't have a list route; use the proverbs route
    return json.dumps(_get("/api/promo/proverbs"), indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Settings
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def settings_get() -> str:
    """
    Get Indaba's current settings (website dir, AI provider, asset prompts, etc.).

    Useful for checking what's configured before publishing or deploying.
    """
    return json.dumps(_get("/api/settings"), indent=2)


@mcp.tool()
def settings_update(updates: str) -> str:
    """
    Update Indaba settings.

    Args:
        updates: JSON string of settings to update. E.g.:
                 '{"website": {"website_dir": "/path/to/site", "auto_deploy": false}}'

    Returns the updated settings.
    """
    data = json.loads(updates)
    return json.dumps(_put("/api/settings", data), indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Hub / Overview
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def hub_summary() -> str:
    """
    Get Indaba's hub summary — pipeline stage counts, recent activity, pending tasks.

    Use this at the start of a session to understand what's in the pipeline and
    what needs attention.
    """
    return json.dumps(_get("/api/hub/summary"), indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
