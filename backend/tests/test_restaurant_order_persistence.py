from unittest.mock import patch

from app.services.gemini import aggregate_items_deterministically
from app.services.order_service import order_service
from app.services.order_amendment_service import normalize_amendment_items
from app.services.store import store


def test_restaurant_variants_are_not_merged():
    items = [
        {
            "name": "Pizza",
            "quantity": 1,
            "unit": "piece",
            "size_variant": "large",
            "add_ons": ["extra cheese"],
        },
        {
            "name": "Pizza",
            "quantity": 1,
            "unit": "piece",
            "size_variant": "small",
            "add_ons": [],
        },
    ]

    assert len(aggregate_items_deterministically(items)) == 2


def test_identical_restaurant_variants_are_merged():
    items = [
        {
            "name": "Paneer Tikka",
            "quantity": 1,
            "unit": "plate",
            "spice_level": "less spicy",
        },
        {
            "name": "Paneer Tikka",
            "quantity": 2,
            "unit": "plate",
            "spice_level": "less spicy",
        },
    ]

    result = aggregate_items_deterministically(items)
    assert len(result) == 1
    assert result[0]["quantity"] == 3


def test_restaurant_fields_survive_order_conversion():
    card_id = "ac_restaurant_persistence"
    store.create(
        {
            "id": card_id,
            "shop_id": "shop-restaurant",
            "customer_name": "Danish",
            "items": [
                {
                    "name": "Paneer Tikka",
                    "quantity": 2,
                    "unit": "plate",
                    "price": 250,
                    "size_variant": "full",
                    "add_ons": ["extra chutney"],
                    "spice_level": "less spicy",
                    "veg_non_veg": "Veg",
                }
            ],
            "takeaway_delivery_dine_in": "Takeaway",
            "special_instructions": "No onion",
            "source": "text",
        }
    )

    try:
        with (
            patch.object(order_service, "supabase", None),
            patch.object(order_service, "_get_and_increment_mock_sequence", return_value=1001),
            patch(
                "app.services.matching_service.matching_service.match_product",
                return_value={"resolution_status": "unmatched"},
            ),
        ):
            order = order_service.convert_action_card_to_order(card_id, "owner")
    finally:
        store._db.pop(card_id, None)

    assert order["fulfillment_type"] == "takeaway"
    assert order["special_instructions"] == "No onion"
    assert order["order_items"][0]["metadata"] == {
        "size_variant": "full",
        "spice_level": "less spicy",
        "veg_non_veg": "Veg",
        "add_ons": ["extra chutney"],
    }


def test_grocery_conversion_remains_backward_compatible():
    card_id = "ac_grocery_compatibility"
    store.create(
        {
            "id": card_id,
            "shop_id": "shop-grocery",
            "items": [{"name": "Atta", "quantity": 5, "unit": "kg", "price": 45}],
            "source": "text",
        }
    )

    try:
        with (
            patch.object(order_service, "supabase", None),
            patch.object(order_service, "_get_and_increment_mock_sequence", return_value=1002),
            patch(
                "app.services.matching_service.matching_service.match_product",
                return_value={"resolution_status": "unmatched"},
            ),
        ):
            order = order_service.convert_action_card_to_order(card_id, "owner")
    finally:
        store._db.pop(card_id, None)

    assert order["fulfillment_type"] is None
    assert order["special_instructions"] is None
    assert order["order_items"][0]["metadata"] == {}


def test_customer_amendment_preserves_restaurant_modifiers():
    with patch(
        "app.services.order_amendment_service.matching_service.match_product",
        return_value={
            "resolution_status": "matched",
            "catalog_item_id": "dish-1",
            "canonical_name": "paneer_tikka",
            "display_name": "Paneer Tikka",
            "unit": "plate",
            "unit_price": 250,
        },
    ):
        items = normalize_amendment_items(
            "restaurant-shop",
            [
                {
                    "name": "Paneer Tikka",
                    "quantity": 2,
                    "unit": "plate",
                    "size_variant": "full",
                    "add_ons": ["extra chutney"],
                    "spice_level": "less spicy",
                    "veg_non_veg": "Veg",
                }
            ],
        )

    assert items[0]["metadata"]["size_variant"] == "full"
    assert items[0]["metadata"]["add_ons"] == ["extra chutney"]
