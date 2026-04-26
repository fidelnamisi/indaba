"""
Contact domain model.
Represents a CRM contact (person with a phone number).
"""
import re


E164_PATTERN = re.compile(r'^\+\d{7,15}$')


def validate_contact(data):
    """Validate contact dict. Returns (is_valid, error_message)."""
    if not data.get('name', '').strip():
        return False, "name is required"
    phone = data.get('phone', '').strip()
    if not phone or not E164_PATTERN.match(phone):
        return False, "Phone must be in E.164 format, e.g. +27821234567"
    return True, None
