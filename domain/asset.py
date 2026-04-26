"""
Asset domain model.
Represents a producible content artifact tied to an entity.
"""


def validate_asset(data):
    """Validate asset dict. Returns (is_valid, error_message)."""
    if not data.get('type'):
        return False, "type is required"
    return True, None
