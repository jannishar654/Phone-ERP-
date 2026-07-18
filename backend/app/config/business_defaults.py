from copy import deepcopy
from typing import Any, Dict, Optional


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
    required_order_fields: Optional[list[str]] = None,
    optional_order_fields: Optional[list[str]] = None,
    allow_partial_quantities: bool = True,
    stage_labels: Optional[Dict[str, str]] = None,
    settings: Optional[Dict[str, Any]] = None,
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
        "Indian restaurant dishes, breads, beverages. Common: biryani, paneer, dal, naan, dosa, thali, pizza, momos, noodles, cold coffee, chai. Sizes: half/full, large/medium/small. Add-ons: extra cheese, paneer, gravy, butter, masala, toppings. Spice: less spicy/kam mirch, medium, spicy/tez, extra spicy. Veg/Non-Veg. Order: takeaway/parcel/pack, delivery, dine-in/table. Examples: '2 paneer tikka, ek less spicy' -> 2+1 dishes with less spicy, 'Table 4 ke liye 3 cold coffee' -> table 4, 'Kal 8 baje 20 veg thali deliver' -> delivery kal 8baje 20 thali, '1 large pizza extra cheese takeaway' -> large pizza extra cheese takeaway, 'Do plate chicken biryani medium spicy parcel' -> 2 chicken biryani medium spicy takeaway",
        "portion",
        {
            "order": "food order",
            "customer": "guest",
            "delivery": "delivery",
            "packer": "kitchen staff",
            "dish": "prepared food item / dish",
            "size_variant": "size: half, full, large, medium, small, regular, jumbo, family pack",
            "add_ons": "extras: extra cheese, paneer, gravy, butter, masala, mayonnaise, salad, chutney, raita",
            "spice_level": "spice: less spicy/kam mirch/less mirchi, medium/medium spicy, spicy/tez/masaledar, extra spicy/bahut tez",
            "veg_non_veg": "Veg/Shakahari or Non-Veg/Mansahari",
            "takeaway_delivery_dine_in": "order type: takeaway/parcel/pack/le kar jayenge, delivery/ghar bhej do/deliver kar do/pahuncha do, dine-in/yahan khaana hai/table/baithe khaana",
            "table_number": "table number for dine-in (e.g. Table 4 / table number chaar)",
            "special_instructions": "special instructions: kam mirch/kam spice, no onion/lahsun, extra butter, extra masala, without garlic",
            "plate": "measure word for a single serving of a dish",
            "half_plate": "half serving (aadha plate)",
            "full_plate": "full serving (pura plate)",
            "packet": "parcel/takeaway pack",
        },
        required_order_fields=[
            "items",
            "quantity",
            "size_variant",
            "add_ons",
            "spice_level",
            "veg_non_veg",
        ],
        optional_order_fields=[
            "customer_name",
            "customer_phone",
            "takeaway_delivery_dine_in",
            "table_number",
            "delivery_address",
            "delivery_time",
            "payment_method",
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
