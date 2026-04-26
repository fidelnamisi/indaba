"""
Broadcast Post routes — generate, approve, queue, send proverb posts.
"""
import os
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request, send_from_directory
from utils.json_store import read_json, write_json
from utils.constants import PROMO_PROVERBS_FILE, PROMO_MESSAGES_FILE, GENERATED_IMAGES_DIR, PROMO_SETTINGS_FILE
from services.distribution_service import push_to_outbox, fetch_ec2_queue
from services.scheduler import auto_schedule

try:
    from capabilities.create.generator import composite_proverb_image, generate_single_post
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

bp = Blueprint('promo_broadcast_post', __name__)


@bp.route('/api/promo/broadcast_post/preview-prompt', methods=['POST'])
def preview_broadcast_post_prompt():
    """Phase 1: generate meaning + image prompt without calling Imagen."""
    if not PIL_AVAILABLE:
        return jsonify({"error": "Pillow not installed."}), 503

    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    unused = [p for p in proverbs_data["proverbs"] if not p.get('used', False)]
    if not unused:
        return jsonify({"error": "All proverbs used."}), 409

    proverb = unused[0]
    try:
        from capabilities.create.generator import generate_prompt_only
        result = generate_prompt_only(proverb)
        return jsonify({
            "proverb_id":   proverb["id"],
            "proverb_text": proverb["text"],
            **result,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@bp.route('/api/promo/broadcast_post/generate', methods=['POST'])
def generate_broadcast_post():
    """Phase 2: generate image + composite. Accepts optional pre-approved prompt."""
    if not PIL_AVAILABLE:
        return jsonify({"error": "Pillow not installed."}), 503

    data            = request.get_json() or {}
    approved_prompt = data.get('image_prompt')
    approved_meaning= data.get('meaning')
    proverb_id      = data.get('proverb_id')

    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}

    if proverb_id:
        proverb = next((p for p in proverbs_data["proverbs"] if p['id'] == proverb_id), None)
        if not proverb:
            return jsonify({"error": "Proverb not found."}), 404
    else:
        unused = [p for p in proverbs_data["proverbs"] if not p.get('used', False)]
        if not unused:
            return jsonify({"error": "All proverbs used."}), 409
        proverb = unused[0]

    try:
        if approved_prompt and approved_meaning:
            from capabilities.create.generator import generate_image_and_composite
            result = generate_image_and_composite(proverb, approved_meaning, approved_prompt)
        else:
            result = generate_single_post(proverb, proverbs_data)
        write_json(PROMO_PROVERBS_FILE, proverbs_data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@bp.route('/api/promo/broadcast_post/bulk_generate', methods=['POST'])
def bulk_generate_broadcast_posts():
    data  = request.get_json() or {}
    count = min(int(data.get('count', 5)), 20)

    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    unused        = [p for p in proverbs_data["proverbs"] if not p.get('used', False)]
    if not unused:
        return jsonify({"error": "No unused proverbs remaining."}), 409

    from capabilities.create.generator import _VARIETY_TOKENS
    results = []
    errors  = []
    for i, proverb in enumerate(unused[:count]):
        try:
            variety_hint = _VARIETY_TOKENS[i % len(_VARIETY_TOKENS)]
            results.append(generate_single_post(proverb, proverbs_data, variety_hint=variety_hint))
        except Exception as e:
            errors.append({"proverb_id": proverb["id"], "error": str(e)})

    write_json(PROMO_PROVERBS_FILE, proverbs_data)
    return jsonify({"generated": len(results), "errors": len(errors), "error_details": errors})


@bp.route('/api/promo/broadcast_post/<proverb_id>/status', methods=['POST'])
def update_broadcast_post_status(proverb_id):
    data    = request.get_json() or {}
    status  = data.get('status')
    allowed = ('approved', 'rejected', 'pending')
    if status not in allowed:
        return jsonify({"error": f"status must be one of: {', '.join(allowed)}"}), 400

    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverb = next((p for p in proverbs_data["proverbs"] if p['id'] == proverb_id), None)
    if not proverb:
        return jsonify({"error": "Not found"}), 404

    proverb['queue_status'] = status
    proverb['updated_at']   = datetime.utcnow().isoformat() + "Z"
    write_json(PROMO_PROVERBS_FILE, proverbs_data)
    return jsonify({"ok": True, "queue_status": status})


@bp.route('/api/promo/broadcast_post/bulk_approve', methods=['POST'])
def bulk_approve_broadcast_posts():
    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    settings      = read_json(PROMO_SETTINGS_FILE) or {}
    schedule      = settings.get('delivery_schedule', {})
    # Always use live EC2 queue as scheduling baseline — prevents stale-local divergence
    live_queue = fetch_ec2_queue()
    if live_queue is not None:
        acc_queue    = live_queue
        ec2_fallback = False
    else:
        existing     = (read_json(PROMO_MESSAGES_FILE) or {"messages": []}).get("messages", [])
        acc_queue    = [m for m in existing if m.get('status') == 'queued']
        ec2_fallback = True
    now           = datetime.utcnow().isoformat() + "Z"
    count         = 0
    ec2_failures  = 0
    pending       = [p for p in proverbs_data["proverbs"] if p.get('queue_status') == 'pending']

    for p in pending:
        scheduled_at = auto_schedule('proverb', acc_queue, schedule, fail_if_full=True)
        if scheduled_at is None:
            write_json(PROMO_PROVERBS_FILE, proverbs_data)
            return jsonify({
                "error": f"Schedule full — only {count} of {len(pending)} proverbs could be queued before running out of slots.",
                "approved": count,
                "ec2_synced": ec2_failures == 0,
                "ec2_failures": ec2_failures,
            }), 409

        p['queue_status'] = 'approved'
        p['updated_at']   = now
        result = push_to_outbox(
            recipient_phone=os.environ.get('GOWA_CHANNEL_ID', ''),
            recipient_name="WA Channel",
            content=p["text"],
            source="wa_post_maker",
            media_url=p.get('composite_path'),
            proverb_id=p['id'],
            scheduled_at=scheduled_at,
        )
        if not result.get('ec2_synced', True):
            ec2_failures += 1
        # Add to accumulator so next proverb picks the next slot
        acc_queue.append({"scheduled_at": scheduled_at, "status": "queued"})
        count += 1

    write_json(PROMO_PROVERBS_FILE, proverbs_data)
    return jsonify({
        "approved":      count,
        "ec2_synced":    ec2_failures == 0,
        "ec2_failures":  ec2_failures,
        "schedule_source": "local_fallback" if ec2_fallback else "ec2_live",
    })


@bp.route('/api/promo/broadcast_post/<proverb_id>/queue', methods=['POST'])
def queue_broadcast_proverb(proverb_id):
    data        = request.get_json() or {}
    force_text  = data.get('force_text', False)
    force_retry = data.get('force_retry', False)

    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverb = next((p for p in proverbs_data["proverbs"] if p['id'] == proverb_id), None)
    if not proverb:
        return jsonify({"error": "Proverb not found"}), 404

    messages_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    existing_queued = any(m.get('proverb_id') == proverb_id and m.get('status') == 'queued'
                          for m in messages_data["messages"])

    if existing_queued and not force_text and not force_retry:
        return jsonify({
            "ok": True,
            "message": "Already scheduled on EC2",
            "already_exists": True
        })

    # If forcing text or retry, remove the existing queued message so push_to_outbox creates a fresh one
    if (force_text or force_retry) and existing_queued:
        messages_data["messages"] = [m for m in messages_data["messages"]
                                     if not (m.get('proverb_id') == proverb_id and m.get('status') == 'queued')]
        write_json(PROMO_MESSAGES_FILE, messages_data)

    channel_id   = os.environ.get('GOWA_CHANNEL_ID', '')
    settings     = read_json(PROMO_SETTINGS_FILE) or {}
    schedule     = settings.get('delivery_schedule', {})
    # Always use live EC2 queue as scheduling baseline — prevents stale-local divergence
    live_queue = fetch_ec2_queue()
    if live_queue is not None:
        queued = live_queue
    else:
        existing = (read_json(PROMO_MESSAGES_FILE) or {"messages": []}).get("messages", [])
        queued   = [m for m in existing if m.get('status') == 'queued']
    scheduled_at = auto_schedule('proverb', queued, schedule, fail_if_full=True)
    if scheduled_at is None:
        return jsonify({"error": "Schedule is full — no available proverb slots in the next 90 days."}), 409

    result = push_to_outbox(
        recipient_phone=channel_id,
        recipient_name="WA Channel",
        content=proverb["text"],
        source="wa_post_maker",
        media_url=proverb.get('composite_path'),
        proverb_id=proverb_id,
        scheduled_at=scheduled_at,
        force_text=force_text
    )

    # Mark proverb as approved/scheduled so it leaves the pending list
    now = datetime.utcnow().isoformat() + "Z"
    proverb['queue_status'] = 'approved'
    proverb['updated_at']   = now
    write_json(PROMO_PROVERBS_FILE, proverbs_data)

    return jsonify({
        "ok": True,
        "message": "Scheduled on EC2",
        "ec2_synced": result.get('ec2_synced', True),
        "error": result.get('error'),
        "scheduled_at": scheduled_at
    })


@bp.route('/api/promo/broadcast_post/<proverb_id>/send', methods=['POST'])
def send_broadcast_post(proverb_id):
    """Send immediately via EC2 (push to queue then trigger send_now)."""
    import requests as _req

    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverb = next((p for p in proverbs_data["proverbs"] if p['id'] == proverb_id), None)
    if not proverb:
        return jsonify({"error": "Proverb not found"}), 404

    composite_path = proverb.get('composite_path')
    if not composite_path or not os.path.exists(composite_path):
        return jsonify({"error": "Composite image not found. Generate the post first."}), 409

    channel_id = os.environ.get('GOWA_CHANNEL_ID', '')
    if not channel_id:
        return jsonify({"error": "GOWA_CHANNEL_ID not set."}), 503

    cloud_url = os.environ.get('EC2_SENDER_URL', '').rstrip('/')
    if not cloud_url:
        return jsonify({"error": "EC2_SENDER_URL not configured."}), 503

    # Step 1: Push to outbox (mirrors to EC2 queue)
    result = push_to_outbox(
        recipient_phone=channel_id,
        recipient_name="WA Channel",
        content=proverb["text"],
        source="wa_post_maker",
        media_url=composite_path,
        proverb_id=proverb_id,
        scheduled_at=None,
    )
    msg_id = result['id']

    # Step 2: Tell EC2 to send it immediately
    try:
        r   = _req.post(f'{cloud_url}/queue/{msg_id}/send_now',
                        auth=('admin', 'admin'), timeout=30)
        res = r.json()
    except Exception as e:
        return jsonify({"error": f"EC2 send_now failed: {e}"}), 502

    if not res.get('ok'):
        return jsonify({"error": f"EC2 send_now error: {res.get('error', 'Unknown')}"}), 502

    # Step 3: Mark proverb as sent
    now = datetime.utcnow().isoformat() + "Z"
    proverb['queue_status'] = 'sent'
    proverb['sent_at']      = now
    proverb['updated_at']   = now
    write_json(PROMO_PROVERBS_FILE, proverbs_data)

    # Update local message record to sent
    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    for m in msgs_data["messages"]:
        if m['id'] == msg_id:
            m['status']     = 'sent'
            m['sent_at']    = now
            m['updated_at'] = now
            break
    write_json(PROMO_MESSAGES_FILE, msgs_data)

    return jsonify({"ok": True, "message_id": msg_id})


@bp.route('/api/promo/broadcast_post/<proverb_id>', methods=['DELETE'])
def delete_broadcast_post(proverb_id):
    """Delete a proverb/post entirely (does not delete the image file)."""
    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    original_len  = len(proverbs_data["proverbs"])
    proverbs_data["proverbs"] = [
        p for p in proverbs_data["proverbs"] if p['id'] != proverb_id
    ]
    if len(proverbs_data["proverbs"]) == original_len:
        return jsonify({"error": "Not found"}), 404
    write_json(PROMO_PROVERBS_FILE, proverbs_data)
    return jsonify({"ok": True})


@bp.route('/api/promo/broadcast_post/<proverb_id>/regen_image', methods=['POST'])
def regen_broadcast_post_image(proverb_id):
    import requests as _req
    import base64 as _b64
    from google.oauth2 import service_account as _sa
    from google.auth.transport.requests import Request as _Req

    proverbs_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    proverb = next((p for p in proverbs_data["proverbs"] if p['id'] == proverb_id), None)
    if not proverb:
        return jsonify({"error": "Not found"}), 404
    if not proverb.get('image_prompt'):
        return jsonify({"error": "No image prompt — generate the post first."}), 409

    sa_path = os.environ.get('GOOGLE_SA_KEY', '')
    if not sa_path or not os.path.exists(sa_path):
        return jsonify({"error": "GOOGLE_SA_KEY not set."}), 503

    try:
        _creds = _sa.Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        _creds.refresh(_Req())

        settings = read_json(PROMO_SETTINGS_FILE) or {}
        full_prompt = (
            proverb['image_prompt']
            + ". Photorealistic, cinematic, 9:16 portrait orientation, "
              "tight intentional framing, subject fills the frame, "
              "no text overlay, no logos, no studio backdrop. "
              "CRITICAL: any human subjects must have visibly dark skin — "
              "Black South African representation, rich dark melanin complexion."
        )
        _img_resp = _req.post(
            "https://us-central1-aiplatform.googleapis.com/v1/projects/"
            "gen-lang-client-0717388888/locations/us-central1/publishers/google/"
            "models/imagen-3.0-generate-001:predict",
            headers={"Authorization": f"Bearer {_creds.token}", "Content-Type": "application/json"},
            json={"instances": [{"prompt": full_prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "9:16", "personGeneration": "allow_all"}},
            timeout=90,
        )
        if _img_resp.status_code != 200:
            return jsonify({"error": f"Imagen error {_img_resp.status_code}"}), 502

        _img_bytes = _b64.b64decode(_img_resp.json()["predictions"][0]["bytesBase64Encoded"])
        os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
        tmp_photo = os.path.join(GENERATED_IMAGES_DIR, '_tmp_photo.jpg')
        with open(tmp_photo, 'wb') as _f:
            _f.write(_img_bytes)

        new_composite = composite_proverb_image(
            photo_url=tmp_photo,
            proverb_text=proverb['text'],
            attribution=proverb.get('origin', 'African') + ' Proverb',
            meaning=proverb['meaning'],
            cta=proverb['cta'],
        )

        now = datetime.utcnow().isoformat() + "Z"
        proverb['composite_path'] = new_composite
        proverb['queue_status']   = 'pending'
        proverb['updated_at']     = now
        write_json(PROMO_PROVERBS_FILE, proverbs_data)

        filename = os.path.basename(new_composite)
        return jsonify({"ok": True, "composite_url": f"/data/images/{filename}"})

    except Exception as e:
        return jsonify({"error": f"Regen failed: {e}"}), 502


@bp.route('/data/images/<filename>')
def serve_generated_image(filename):
    return send_from_directory(GENERATED_IMAGES_DIR, filename)
