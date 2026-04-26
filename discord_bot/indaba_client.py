"""
Indaba HTTP client — mirrors the MCP server tools as simple Python calls.
"""
import httpx
import json
from config import INDABA_BASE_URL

TIMEOUT = 30.0


def _get(path: str, params: dict | None = None) -> dict:
    url = f"{INDABA_BASE_URL}{path}"
    with httpx.Client(timeout=TIMEOUT) as c:
        r = c.get(url, params=params)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict | None = None) -> dict:
    url = f"{INDABA_BASE_URL}{path}"
    with httpx.Client(timeout=TIMEOUT) as c:
        r = c.post(url, json=body or {})
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError:
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:400]
        raise RuntimeError(f"HTTP {r.status_code}: {detail}")
    return r.json()


def _put(path: str, body: dict) -> dict:
    url = f"{INDABA_BASE_URL}{path}"
    with httpx.Client(timeout=TIMEOUT) as c:
        r = c.put(url, json=body)
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError:
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:400]
        raise RuntimeError(f"HTTP {r.status_code}: {detail}")
    return r.json()


# ── Hub ───────────────────────────────────────────────────────────────────────

def hub_summary() -> dict:
    return _get("/api/hub/summary")


# ── Pipeline ──────────────────────────────────────────────────────────────────

def pipeline_list(book: str = "", stage: str = "") -> list:
    entries = _get("/api/content-pipeline")
    if book:
        entries = [e for e in entries if e.get("book") == book.upper()]
    if stage:
        entries = [e for e in entries if e.get("workflow_stage") == stage]
    return entries


def pipeline_get(entry_id: str) -> dict:
    return _get(f"/api/content-pipeline/{entry_id}")


def pipeline_set_stage(entry_id: str, stage: str) -> dict:
    return _put(f"/api/content-pipeline/{entry_id}/workflow-stage", {"stage": stage})


# ── Website ───────────────────────────────────────────────────────────────────

def website_publish(entry_id: str) -> dict:
    return _post("/api/website/publish", {"entry_id": entry_id})


def website_deploy() -> dict:
    return _post("/api/website/deploy")


def website_deploy_status() -> dict:
    return _get("/api/website/deploy-status")


def website_work_sync(work_id: str) -> dict:
    return _get(f"/api/website/work-sync/{work_id}")


# ── Works ─────────────────────────────────────────────────────────────────────

def works_list() -> dict:
    return _get("/api/catalog-works")


# ── EC2 Sender (direct — bypasses Indaba) ────────────────────────────────────

def ec2_sender_health() -> dict:
    import os
    ec2_url = os.environ.get("EC2_SENDER_URL", "http://localhost:5555")
    url = f"{ec2_url}/health"
    with httpx.Client(timeout=10.0) as c:
        r = c.get(url)
    return r.json()


# ── Settings ──────────────────────────────────────────────────────────────────

def settings_get() -> dict:
    return _get("/api/settings")


# ── Promo Broadcast ───────────────────────────────────────────────────────────

def promo_broadcast_list() -> list:
    return _get("/api/promo/proverbs")


def promo_broadcast_generate(proverb_id: str) -> dict:
    return _post("/api/promo/broadcast_post/generate", {"proverb_id": proverb_id})


def promo_broadcast_queue(proverb_id: str, channel: str = "channel") -> dict:
    return _post(f"/api/promo/broadcast_post/{proverb_id}/queue", {"channel": channel})


# ── Flash Fiction ─────────────────────────────────────────────────────────────

def flash_fiction_generate(params: dict) -> dict:
    return _post("/api/flash-fiction/generate", params)


# ── Asset generation ──────────────────────────────────────────────────────────

def generate_asset(entry_id: str, asset_type: str) -> dict:
    return _post(f"/api/modules/{entry_id}/generate-asset", {"asset_type": asset_type})


# ── Phase 1 additions ─────────────────────────────────────────────────────────

def works_get(work_id: str) -> dict:
    return _get(f"/api/works/{work_id}")


def work_queue_module(work_id: str, module_id: str, cta_url: str = "") -> dict:
    body = {}
    if cta_url:
        body["cta_url"] = cta_url
    return _post(f"/api/works/{work_id}/modules/{module_id}/queue", body)


def scheduler_run(dry_run: bool = False) -> dict:
    return _post("/api/scheduler/run", {"dry_run": dry_run})


def scheduler_preview() -> dict:
    return _get("/api/scheduler/preview")


def proverbs_create_batch(proverbs: list) -> dict:
    return _post("/api/promo/proverbs/import_bulk", {"proverbs": proverbs})


def flash_fiction_publish_queue(pipeline_entry_id: str, work_id: str, module_id: str) -> dict:
    """Publish a pipeline entry to the website, then queue the work module with the live URL as CTA."""
    publish_result = _post("/api/website/publish", {"entry_id": pipeline_entry_id})
    chapter_url = (publish_result.get("website_publish_info") or {}).get("chapter_url", "")
    queue_result = work_queue_module(work_id, module_id, cta_url=chapter_url)
    return {
        "published": publish_result,
        "queued": queue_result,
        "chapter_url": chapter_url,
    }


def audio_browse(work_id: str) -> dict:
    return _get(f"/api/audio/browse/{work_id}")


def audio_upload(work_id: str, filename: str, module_id: str, chapter_number=None) -> dict:
    body: dict = {"work_id": work_id, "filename": filename, "module_id": module_id}
    if chapter_number is not None:
        body["chapter_number"] = chapter_number
    return _post("/api/audio/upload", body)


def crm_leads_summary() -> dict:
    return _get("/api/promo/pipeline")
