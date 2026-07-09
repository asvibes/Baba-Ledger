from .invoice import PROFILE as INVOICE_PROFILE
from .tender import PROFILE as TENDER_PROFILE
from .contract import PROFILE as CONTRACT_PROFILE
from .work_order import PROFILE as WORK_ORDER_PROFILE
from .purchase_order import PROFILE as PURCHASE_ORDER_PROFILE
from .boq import PROFILE as BOQ_PROFILE
from .delivery_challan import PROFILE as DELIVERY_CHALLAN_PROFILE
from .technical_spec import PROFILE as TECHNICAL_SPEC_PROFILE
from .generic import PROFILE as GENERIC_PROFILE

PROFILE_REGISTRY = {
    "invoice": INVOICE_PROFILE,
    "tender": TENDER_PROFILE,
    "contract": CONTRACT_PROFILE,
    "work_order": WORK_ORDER_PROFILE,
    "purchase_order": PURCHASE_ORDER_PROFILE,
    "boq": BOQ_PROFILE,
    "delivery_challan": DELIVERY_CHALLAN_PROFILE,
    "technical_spec": TECHNICAL_SPEC_PROFILE,
    "generic": GENERIC_PROFILE,
}

def get_profile(document_type: str):
    """Return the profile for a document type."""
    return PROFILE_REGISTRY.get(document_type, GENERIC_PROFILE)