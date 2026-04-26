"""
Distribution service — outbox management, GOWA delivery, cloud mirroring.
"""
import os
import json
import uuid
import requests as _req
from datetime import datetime

from utils.json_store import read_json, write_json, DATA_DIR
from utils.constants import PROMO_MESSAGES_FILE, PROMO_PROVERBS_FILE


# ── Outbox helpers ─────────────────────────────────────────────────────────────

_BROADCAST_PREFIXES = ("[Post] ", "[Image post] ", "[Post]", "[Image post]")

def push_to_outbox(recipient_phone, recipient_name, content,
                   source, scheduled_at=None, media_url=None, **kwargs):
    """Add a message to the unified outbox (promo_messages.json).
    Returns dict: {"id": msg_id, "ec2_synced": bool}
    """
    # Defensive: broadcast posts must never carry internal prefixes
    if source in ("wa_post_maker", "work_serializer"):
        for prefix in _BROADCAST_PREFIXES:
            if content.startswith(prefix):
                content = content[len(prefix):]
                break

    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now       = datetime.utcnow().isoformat() + "Z"
    msg_id    = str(uuid.uuid4())

    new_msg = {
        "id":               msg_id,
        "recipient_phone":  recipient_phone,
        "recipient_name":   recipient_name,
        "content":          content,
        "status":           "queued",
        "source":           source,
        "scheduled_at":     scheduled_at,
        "media_url":        media_url,
        "created_at":       now,
        "updated_at":       now,
    }
    new_msg.update(kwargs)  # allow extra metadata (lead_id, proverb_id, etc.)

    msgs_data["messages"].append(new_msg)
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    ec2_ok = _mirror_to_cloud(new_msg)
    return {"id": msg_id, "ec2_synced": ec2_ok}


def write_cowork_job(message):
    """Write a cowork job file for Cowork-based delivery."""
    try:
        job_dir  = os.path.join(DATA_DIR, 'cowork_jobs')
        os.makedirs(job_dir, exist_ok=True)
        job_file = os.path.join(job_dir, f"{message['id']}.json")
        job_data = {
            "message_id":       message["id"],
            "recipient_phone":  message["recipient_phone"],
            "recipient_name":   message["recipient_name"],
            "content":          message["content"],
            "media_url":        message.get("media_url"),  # Added to support image delivery
            "created_at":       datetime.utcnow().isoformat() + "Z",
        }
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(job_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error writing cowork job: {e}")
        return False


# ── GOWA delivery ──────────────────────────────────────────────────────────────

def send_gowa_message(msg):
    """Send a message via GOWA. Returns {'ok': bool, ...}."""
    import requests as _req
    gowa_url  = os.environ.get('GOWA_BASE_URL', 'http://localhost:3001')
    device_id = os.environ.get('GOWA_DEVICE_ID', '')
    gowa_auth = os.environ.get('GOWA_AUTH', 'admin:admin')

    if not device_id:
        return {"ok": False, "error": "GOWA_DEVICE_ID not set"}

    raw_content = msg["content"]
    is_proverb  = msg.get("source") == "wa_post_maker"

    is_image = (msg.get('media_url') and
                str(msg['media_url']).lower().endswith(('.jpg', '.jpeg', '.png')))

    # HARD ENFORCEMENT: Broadcast proverbs MUST be images. Never revert to text.
    if is_proverb and not is_image:
        print(f"[GOWA] Critical: Broadcast post {msg.get('id')} missing image. Aborting delivery.")
        return {"ok": False, "error": "Broadcast posts must be images."}

    endpoint = f"{gowa_url}/send/image" if is_image else f"{gowa_url}/send/text"

    payload = {"phone": msg["recipient_phone"]}
    if is_image:
        filename        = os.path.basename(msg['media_url'])
        payload["image_url"] = f"http://host.docker.internal:5050/data/images/{filename}"
        payload["caption"]   = "" if is_proverb else raw_content
    else:
        payload["message"] = raw_content

    auth_parts = gowa_auth.split(':', 1)
    auth       = (auth_parts[0], auth_parts[1]) if len(auth_parts) == 2 else ("admin", "admin")

    try:
        resp = _req.post(
            endpoint,
            json=payload,
            headers={"X-Device-Id": device_id},
            auth=auth,
            timeout=60,
        )
        data = resp.json()
        if data.get("code") == "SUCCESS":
            return {"ok": True, "message_id": msg["id"]}
        return {"ok": False, "error": f"GOWA: {data.get('message', 'Unknown error')}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def mark_proverb_sent(proverb_id, status, now):
    """Update a proverb's queue_status after a send attempt."""
    p_data = read_json(PROMO_PROVERBS_FILE) or {"proverbs": []}
    for p in p_data["proverbs"]:
        if p["id"] == proverb_id:
            p["queue_status"] = status
            if status == "sent":
                p["sent_at"] = now
            break
    write_json(PROMO_PROVERBS_FILE, p_data)


# ── EC2 sync helpers ──────────────────────────────────────────────────────────

def fetch_ec2_queue():
    """Fetch the live queue from EC2 Sender. Returns list of queued-status messages, or None on failure.

    Use this as the source of truth when scheduling new messages — it reflects actual EC2 state,
    not a potentially stale local mirror.
    """
    cloud_url = os.environ.get('EC2_SENDER_URL', '').rstrip('/')
    if not cloud_url:
        return None
    try:
        r = _req.get(f'{cloud_url}/queue', auth=('admin', 'admin'), timeout=10)
        if r.status_code == 200:
            all_msgs = r.json()
            return [m for m in all_msgs if m.get('status') == 'queued']
        return None
    except Exception:
        return None


def _ec2_delete(msg_id):
    """Delete a message from EC2 queue. Returns True on success or if EC2 not configured."""
    cloud_url = os.environ.get('EC2_SENDER_URL', '').rstrip('/')
    if not cloud_url:
        return True
    try:
        r = _req.post(f'{cloud_url}/queue/{msg_id}/delete',
                      auth=('admin', 'admin'), timeout=10)
        return r.json().get('ok', False)
    except Exception:
        return False


def _ec2_update(msg_id, fields):
    """Update a queued message on EC2. Returns True on success or if EC2 not configured."""
    cloud_url = os.environ.get('EC2_SENDER_URL', '').rstrip('/')
    if not cloud_url:
        return True
    try:
        r = _req.put(f'{cloud_url}/queue/{msg_id}',
                     json=fields, auth=('admin', 'admin'), timeout=10)
        return r.json().get('ok', False)
    except Exception:
        return False


# ── Cloud mirroring ────────────────────────────────────────────────────────────

def _upload_image_to_s3(local_path):
    """Upload a local image file to S3 and return (public_url, error_message).
    The bucket has a public read policy on images/* so URLs never expire.
    """
    try:
        import boto3, mimetypes
        from botocore.config import Config
        bucket = os.environ.get('INDABA_S3_BUCKET')
        if not bucket:
            return None, "INDABA_S3_BUCKET not set"

        s3 = boto3.client('s3',
                          region_name='us-east-1',
                          config=Config(signature_version='s3v4'))

        key = 'images/' + os.path.basename(local_path)
        content_type = mimetypes.guess_type(local_path)[0] or 'image/jpeg'

        s3.upload_file(local_path, bucket, key, ExtraArgs={'ContentType': content_type})

        # Use permanent public URL — bucket policy allows public GetObject on images/*
        public_url = f"https://{bucket}.s3.amazonaws.com/{key}"
        return public_url, None
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, f"S3 upload failed: {str(e)}"


def _mirror_to_cloud(msg, force_text=False):
    """Push a queued message to the EC2 Indaba Sender."""
    import requests as _req
    cloud_url = os.environ.get('EC2_SENDER_URL', '').rstrip('/')
    if not cloud_url:
        return False, "EC2_SENDER_URL not configured"
        
    try:
        cloud_msg = dict(msg)
        media_url = cloud_msg.get('media_url', '')
        
        if media_url and not media_url.startswith('http'):
            if force_text:
                cloud_msg.pop('media_url', None)
            else:
                # Persistent S3 Delivery
                s3_url, s3_err = _upload_image_to_s3(media_url)
                if s3_url:
                    cloud_msg['media_url'] = s3_url
                elif not force_text and cloud_msg.get('source') == 'wa_post_maker':
                    return False, s3_err
                else:
                    cloud_msg.pop('media_url', None)

        r = _req.post(f'{cloud_url}/queue', json=cloud_msg, auth=('admin', 'admin'), timeout=30)
        
        if r.status_code in (200, 201):
            return True, None
        else:
            try:
                err_msg = r.json().get('error', f'Status {r.status_code}')
            except:
                err_msg = f'Status {r.status_code}'
            return False, f"EC2 sync failed: {err_msg}"
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Cloud sync error: {str(e)}"


def push_to_outbox(recipient_phone, recipient_name, content,
                   source, scheduled_at=None, media_url=None, force_text=False, **kwargs):
    """Add a message to the unified outbox. Returns dict with 'ec2_synced' and 'error'."""
    # Defensive: broadcast posts must never carry internal prefixes
    if source in ("wa_post_maker", "work_serializer"):
        for prefix in _BROADCAST_PREFIXES:
            if content.startswith(prefix):
                content = content[len(prefix):]
                break

    msgs_data = read_json(PROMO_MESSAGES_FILE) or {"messages": []}
    now       = datetime.utcnow().isoformat() + "Z"
    msg_id    = str(uuid.uuid4())

    new_msg = {
        "id":               msg_id,
        "recipient_phone":  recipient_phone,
        "recipient_name":   recipient_name,
        "content":          content,
        "status":           "queued",
        "source":           source,
        "scheduled_at":     scheduled_at,
        "media_url":        media_url,
        "created_at":       now,
        "updated_at":       now,
    }
    new_msg.update(kwargs)

    msgs_data["messages"].append(new_msg)
    write_json(PROMO_MESSAGES_FILE, msgs_data)
    
    ec2_ok, ec2_err = _mirror_to_cloud(new_msg, force_text=force_text)
    return {"id": msg_id, "ec2_synced": ec2_ok, "error": ec2_err}
