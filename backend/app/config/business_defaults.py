from copy import deepcopy
from typing import Any, Dict


# These stages match the existing orders.lifecycle_status constraint and routes.
# Business-specific wording belongs in settings.stage_labels until the lifecycle
# engine itself supports custom states.
CANONICAL_WORKFLOW_STAGES = [
    "pending_review",
    "packing",
    "out_for_delivery",
    "delivered",
    "cancelled",
]

CANONICAL_TRANSITIONS = {
    "pending_review": ["packing", "cancelled"],
    "packing": ["out_for_delivery", "cancelled"],
    "out_for_delivery": ["delivered", "cancelled"],
    "delivered": [],
    "cancelled": [],
}


def _default(
    business_type: str,
    display_name: str,
    common_items_hint: str,
    default_unit: str,
    terminology: Dict[str, str],
    *,
    required_order_fields: list[str] | None = None,
    optional_order_fields: list[str] | None = None,
    allow_partial_quantities: bool = True,
    stage_labels: Dict[str, str] | None = None,
    settings: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    merged_settings: Dict[str, Any] = {
        "workflow_transitions": deepcopy(CANONICAL_TRANSITIONS),
        "stage_labels": stage_labels or {},
    }
    if settings:
        merged_settings.update(settings)

    return {
        "business_type": business_type,
        "display_name": display_name,
        "required_order_fields": required_order_fields or ["items"],
        "optional_order_fields": optional_order_fields
        or [
            "customer_name",
            "customer_phone",
            "delivery_address",
            "delivery_time",
            "payment_method",
        ],
        "workflow_stages": list(CANONICAL_WORKFLOW_STAGES),
        "extraction_context": {
            "default_unit": default_unit,
            "allow_partial_quantities": allow_partial_quantities,
            "common_items_hint": common_items_hint,
        },
        "terminology": terminology,
        "settings": merged_settings,
    }


BUSINESS_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "grocery": _default(
        "grocery",
        "Grocery Store",
        "atta, rice, pulses, oil, sugar, spices, produce, and household items",
        "piece",
        {
            "order": "order",
            "customer": "customer",
            "delivery": "delivery",
            "packer": "packer",
        },
    ),
    "wholesale": _default(
        "wholesale",
        "Wholesale Business",
        "bulk grocery, cartons, sacks, cases, wholesale packs, and repeat orders",
        "piece",
        {
            "order": "bulk order",
            "customer": "buyer",
            "delivery": "dispatch",
            "packer": "warehouse staff",
        },
    ),
    "restaurant": _default(
        "restaurant",
        "Restaurant",
        "prepared dishes, breads, beverages, add-ons, portions, and meal customizations",
        "portion",
        {
            "order": "food order",
            "customer": "guest",
            "delivery": "delivery",
            "packer": "kitchen staff",
        },
        optional_order_fields=[
            "customer_name",
            "customer_phone",
            "delivery_address",
            "delivery_time",
            "table_number",
            "special_instructions",
        ],
        allow_partial_quantities=False,
        stage_labels={"packing": "Preparing"},
    ),
    "pharmacy": _default(
        "pharmacy",
        "Pharmacy",
        "medicines, strips, syrups, health products, and prescription items",
        "strip",
        {
            "order": "medicine request",
            "customer": "customer",
            "delivery": "delivery",
            "packer": "pharmacy staff",
        },
        optional_order_fields=[
            "customer_name",
            "customer_phone",
            "delivery_address",
            "delivery_time",
            "prescription_details",
        ],
        allow_partial_quantities=False,
        stage_labels={"pending_review": "Prescription Review"},
        settings={
            "requires_human_review": True,
            "medical_advice_disabled": True,
        },
    ),
    "bakery": _default(
        "bakery",
        "Bakery",
        "cakes, pastries, breads, cookies, weights, flavors, and custom messages",
        "piece",
        {
            "order": "bakery order",
            "customer": "customer",
            "delivery": "delivery",
            "packer": "bakery staff",
        },
        optional_order_fields=[
            "customer_name",
            "customer_phone",
            "delivery_address",
            "delivery_time",
            "pickup_time",
            "custom_message",
            "special_instructions",
        ],
        stage_labels={"packing": "Preparing"},
    ),
    "hardware": _default(
        "hardware",
        "Hardware Store",
        "tools, paint, fasteners, electrical, plumbing, and building materials",
        "piece",
        {
            "order": "order",
            "customer": "customer",
            "delivery": "dispatch",
            "packer": "warehouse staff",
        },
        optional_order_fields=[
            "customer_name",
            "customer_phone",
            "delivery_address",
            "delivery_time",
            "project_reference",
        ],
    ),
    "general": _default(
        "general",
        "General Business",
        "products or services sold by this business",
        "piece",
        {
            "order": "order",
            "customer": "customer",
            "delivery": "fulfilment",
            "packer": "operations staff",
        },
    ),
}


def get_business_default(business_type: str) -> Dict[str, Any]:
    """Return an isolated copy so callers cannot mutate process-wide defaults."""
    return deepcopy(BUSINESS_DEFAULTS[business_type])
