"""
Sales pipeline capability.
Manages deal stage transitions in the CRM.
"""
from utils.constants import LEAD_STAGES
from services.crm_service import update_deal_stage, get_pipeline


def advance_deal(lead_id, new_stage):
    """Move a deal to a new stage. Returns updated deal or raises ValueError."""
    if new_stage not in LEAD_STAGES:
        raise ValueError(f"Invalid stage '{new_stage}'. Must be one of: {LEAD_STAGES}")
    return update_deal_stage(lead_id, new_stage)


def get_open_deals():
    """Return all deals not in 'won' or 'lost' stage."""
    return [l for l in get_pipeline() if l.get('stage') not in ('won', 'lost')]


def get_deals_won_this_month(month_start_iso):
    """Return deals won since month_start_iso."""
    return [l for l in get_pipeline()
            if l.get('stage') == 'won' and l.get('updated_at', '') >= month_start_iso]


def get_deals_lost_this_month(month_start_iso):
    """Return deals lost since month_start_iso."""
    return [l for l in get_pipeline()
            if l.get('stage') == 'lost' and l.get('updated_at', '') >= month_start_iso]
