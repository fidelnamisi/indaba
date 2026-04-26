"""
Deal domain model.
Represents a sales lead / deal in the CRM pipeline.
"""
from utils.constants import LEAD_STAGES


def validate_deal(data):
    """Validate deal dict. Returns (is_valid, error_message)."""
    if not data.get('contact_id'):
        return False, "contact_id is required"
    if not data.get('product', '').strip():
        return False, "product is required"
    if not data.get('product_type'):
        return False, "product_type is required"
    return True, None


def validate_stage(stage):
    """Returns True if stage is valid."""
    return stage in LEAD_STAGES
