from ..asset_manager import update_asset, get_asset, create_promo_message, read_json

def handle_promote(action, all_assets):
    """
    Executes actual promotion by pushing to the Universal Outbox (The Bucket).
    """
    asset_id = action.get("asset_id")
    if not asset_id: return {"success": False, "error": "Missing asset_id"}
    
    asset = get_asset(asset_id)
    if not asset: return {"success": False, "error": "Asset not found"}
    
    # 1. Fetch distribution settings (from settings.json)
    settings = read_json('promo_settings.json') or {}
    wa_config = settings.get("publishing_wa_recipients", {})
    channel_phone = wa_config.get("channel_id")

    if not channel_phone:
        return {"success": False, "error": "WhatsApp Channel ID not configured in Settings → WhatsApp Recipients."}

    # 2. Push to Universal Outbox (The Bucket)
    # We use the asset's 'content' which should have been populated by 'produce'
    content = asset.get("content", "")
    if not content:
        return {"success": False, "error": "Cannot promote asset with empty content. Run 'Produce' first."}

    # Format the message (could add branding/template here)
    msg_data = {
        "recipient_phone": channel_phone,
        "recipient_name":  wa_config.get("channel_label", "WA Channel"),
        "content":         content,
        "source":          "asset_promotion_pipeline",
        "source_ref":      {"asset_id": asset_id, "type": asset.get("type")}
    }
    
    msg = create_promo_message(msg_data)
    
    # 3. Update Registry Status
    update_asset(asset_id, {"status": {"promotion": "scheduled"}})
    
    return {"success": True, "details": f"Queued for {msg['recipient_name']} (ID: {msg['id']})"}
