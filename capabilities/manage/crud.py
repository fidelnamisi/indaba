"""
CRUD orchestration capability.
Thin orchestration layer over service CRUD operations.
"""
from services.asset_manager import (
    list_assets, get_asset, create_asset, update_asset, delete_asset,
    list_modules, update_module, delete_module, delete_work,
    # backwards-compat aliases
    list_chapters, update_chapter, delete_chapter, delete_book
)
from services.crm_service import (
    list_contacts, get_contact, create_contact, update_contact, delete_contact,
    get_pipeline, create_deal, update_deal_stage
)

__all__ = [
    'list_assets', 'get_asset', 'create_asset', 'update_asset', 'delete_asset',
    'list_modules', 'update_module', 'delete_module', 'delete_work',
    'list_chapters', 'update_chapter', 'delete_chapter', 'delete_book',
    'list_contacts', 'get_contact', 'create_contact', 'update_contact', 'delete_contact',
    'get_pipeline', 'create_deal', 'update_deal_stage',
]
