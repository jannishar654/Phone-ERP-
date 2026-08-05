from unittest.mock import MagicMock, patch

import pytest

from app.config.business_defaults import (
    BUSINESS_DEFAULTS,
    CANONICAL_WORKFLOW_STAGES,
    get_business_default,
)
from app.schemas.action_card import ActionCard, Item
from app.schemas.business_config import BusinessType
from app.schemas.inbound import NormalizedInboundMessage
from app.services.business_config_service import (
    BusinessConfigService,
    business_config_service,
)
from app.services.gemini import GeminiService
from app.services.intent_router import (
    CatalogItemUnavailableError,
    IntentRouter,
)
from app.services.matching_service import matching_service


def make_query(data=None):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.insert.return_value = query
    query.execute.return_value = MagicMock(data=data or [])
    return query


class TestRestaurantDefaults:

    def test_restaurant_requires_only_items(self):
        config = get_business_default("restaurant")
        assert config["required_order_fields"] == ["items"]

    def test_restaurant_has_all_optional_fields(self):
        config = get_business_default("restaurant")
        expected = {
            "quantity", "size_variant", "add_ons", "spice_level", "veg_non_veg",
            "customer_name", "customer_phone",
            "takeaway_delivery_dine_in", "table_number",
            "delivery_address", "delivery_time",
            "payment_method", "special_instructions",
        }
        assert set(config["optional_order_fields"]) == expected

    def test_restaurant_uses_canonical_workflow_stages(self):
        config = get_business_default("restaurant")
        assert config["workflow_stages"] == CANONICAL_WORKFLOW_STAGES

    def test_restaurant_terminology_contains_critical_keys(self):
        config = get_business_default("restaurant")
        terms = config["terminology"]
        assert "dish" in terms
        assert "size_variant" in terms
        assert "add_ons" in terms
        assert "spice_level" in terms
        assert "veg_non_veg" in terms
        assert "takeaway_delivery_dine_in" in terms
        assert "table_number" in terms
        assert "special_instructions" in terms

    def test_restaurant_hindi_hinglish_terms_in_terminology(self):
        config = get_business_default("restaurant")
        terms = config["terminology"]
        spice = terms.get("spice_level", "").lower()
        assert "kam mirch" in spice or "less spicy" in spice
        assert "tez" in spice or "spicy" in spice
        order_type = terms.get("takeaway_delivery_dine_in", "").lower()
        assert "ghar bhej do" in order_type or "deliver" in order_type
        assert "parcel" in order_type or "takeaway" in order_type

    def test_restaurant_extraction_context_has_examples(self):
        config = get_business_default("restaurant")
        hint = config["extraction_context"]["common_items_hint"]
        assert "paneer tikka" in hint
        assert "cold coffee" in hint
        assert "veg thali" in hint
        assert "pizza" in hint
        assert "chicken biryani" in hint

    def test_restaurant_allow_partial_quantities_is_false(self):
        config = get_business_default("restaurant")
        assert config["extraction_context"]["allow_partial_quantities"] is False

    def test_restaurant_default_unit_is_portion(self):
        config = get_business_default("restaurant")
        assert config["extraction_context"]["default_unit"] == "portion"

    def test_restaurant_has_stage_labels(self):
        config = get_business_default("restaurant")
        assert config["settings"]["stage_labels"]["packing"] == "Preparing"


class TestRestaurantConfigIntegration:

    def test_out_of_stock_restaurant_item_is_not_orderable(self):
        with patch(
            "app.services.catalog_service.catalog_service.get_items_by_shop",
            return_value=[
                {
                    "id": "dish-1",
                    "canonical_name": "paneer_tikka",
                    "display_name": "Paneer Tikka",
                    "base_price": 250,
                    "unit": "plate",
                    "active": True,
                    "in_stock": False,
                    "aliases": ["paneer tikka"],
                }
            ],
        ):
            result = matching_service.match_product(
                "paneer tikka", "restaurant-shop"
            )

        assert result["resolution_status"] == "unmatched"

    def test_restaurant_context_loads_active_in_stock_menu_items(self):
        shop_query = MagicMock()
        shop_query.select.return_value = shop_query
        shop_query.eq.return_value = shop_query
        shop_query.execute.return_value = MagicMock(
            data=[{"name": "PhoneERP Test Kitchen"}]
        )

        catalog_query = MagicMock()
        catalog_query.select.return_value = catalog_query
        catalog_query.eq.return_value = catalog_query
        catalog_query.limit.return_value = catalog_query
        catalog_query.execute.return_value = MagicMock(
            data=[
                {
                    "canonical_name": "paneer_tikka",
                    "display_name": "Paneer Tikka",
                    "category": "Starters",
                }
            ]
        )

        database = MagicMock()
        database.table.side_effect = lambda table: (
            shop_query if table == "shops" else catalog_query
        )
        with (
            patch(
                "app.services.intent_router.supabase_client", database
            ),
            patch.object(
                business_config_service,
                "build_extraction_context",
                return_value={"business_type": "restaurant"},
            ),
        ):
            context = IntentRouter._get_business_context(
                "restaurant-shop", {}
            )

        assert context["offerings"] == ["Paneer Tikka"]
        catalog_query.eq.assert_any_call("shop_id", "restaurant-shop")
        catalog_query.eq.assert_any_call("active", True)
        catalog_query.eq.assert_any_call("in_stock", True)

    def test_build_extraction_context_contains_restaurant_fields(self):
        from app.schemas.business_config import BusinessConfiguration, BusinessType
        service = BusinessConfigService()
        defaults = get_business_default("restaurant")
        restaurant = BusinessConfiguration(
            shop_id="shop",
            id="rest-config",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            business_type=BusinessType.restaurant,
            display_name=defaults["display_name"],
            required_order_fields=defaults["required_order_fields"],
            optional_order_fields=defaults["optional_order_fields"],
            workflow_stages=defaults["workflow_stages"],
            extraction_context=defaults["extraction_context"],
            terminology=defaults["terminology"],
            settings=defaults["settings"],
        )
        with patch.object(service, "get_config", return_value=restaurant):
            context = service.build_extraction_context("shop")
        assert context["business_type"] == "restaurant"
        assert context["required_order_fields"] == ["items"]
        assert "size_variant" in context["optional_order_fields"]

    def test_normalize_business_context_passes_restaurant_fields(self):
        config = get_business_default("restaurant")
        context = GeminiService._normalize_business_context({
            "business_type": "restaurant",
            "required_order_fields": config["required_order_fields"],
            "optional_order_fields": config["optional_order_fields"],
            "terminology": config["terminology"],
            "default_unit": config["extraction_context"]["default_unit"],
            "allow_partial_quantities": config["extraction_context"]["allow_partial_quantities"],
            "common_items_hint": config["extraction_context"]["common_items_hint"],
        })
        assert context["business_type"] == "restaurant"
        assert context["required_order_fields"] == ["items"]
        assert len(context["terminology"]) > 0

    def test_format_business_rules_includes_restaurant_terminology(self):
        config = get_business_default("restaurant")
        context = GeminiService._normalize_business_context({
            "business_type": "restaurant",
            "required_order_fields": config["required_order_fields"],
            "optional_order_fields": config["optional_order_fields"],
            "terminology": config["terminology"],
            "default_unit": config["extraction_context"]["default_unit"],
            "allow_partial_quantities": config["extraction_context"]["allow_partial_quantities"],
            "common_items_hint": config["extraction_context"]["common_items_hint"],
        })
        rules = GeminiService._format_business_rules(context)
        assert "Business Type: restaurant" in rules
        assert "size_variant" in rules
        assert "spice_level" in rules
        assert "takeaway_delivery_dine_in" in rules

    def test_restaurant_menu_rejects_an_unmatched_item(self):
        message = NormalizedInboundMessage(
            shop_id="restaurant-shop",
            customer_id="customer-1",
            channel="meta_whatsapp",
            provider_message_id="wamid-menu-reject",
            message_type="text",
            raw_text="5 kilo aata bhej dena",
        )
        unmatched = Item(
            name="aata",
            raw_name="aata",
            quantity=5,
            unit="kg",
            resolution_status="unmatched",
        )

        with (
            patch.object(
                IntentRouter,
                "_get_customer",
                return_value={
                    "name": "Danish",
                    "phone": "919000000000",
                    "default_address": "Batla House",
                },
            ),
            patch(
                "app.routes.endpoints._safe_items_from_extracted",
                return_value=[unmatched],
            ),
        ):
            with pytest.raises(CatalogItemUnavailableError):
                IntentRouter._build_card_data(
                    {
                        "customer_name": "Danish",
                        "items": [
                            {"name": "aata", "quantity": 5, "unit": "kg"}
                        ],
                    },
                    message,
                    "inbound-menu-reject",
                    {
                        "business_type": "restaurant",
                        "offerings": ["Paneer Tikka", "Veg Thali"],
                    },
                )

    def test_restaurant_menu_accepts_a_matched_dish(self):
        message = NormalizedInboundMessage(
            shop_id="restaurant-shop",
            customer_id="customer-1",
            channel="meta_whatsapp",
            provider_message_id="wamid-menu-accept",
            message_type="text",
            raw_text=(
                "2 paneer tikka less spicy delivery kal 8 baje "
                "Batla House bhej dena"
            ),
        )
        matched = Item(
            name="Paneer Tikka",
            raw_name="paneer tikka",
            quantity=2,
            unit="plate",
            price=250,
            resolution_status="matched",
            spice_level="less spicy",
            veg_non_veg="Veg",
        )

        with (
            patch.object(
                IntentRouter,
                "_get_customer",
                return_value={
                    "name": "Danish",
                    "phone": "919000000000",
                    "default_address": "Batla House",
                },
            ),
            patch(
                "app.routes.endpoints._safe_items_from_extracted",
                return_value=[matched],
            ),
            patch(
                "app.services.time_parser.parse_delivery_time",
                return_value={
                    "normalized": "2026-08-03 8:00 PM",
                    "confidence": 0.95,
                    "warning": None,
                },
            ),
        ):
            card = IntentRouter._build_card_data(
                {
                    "customer_name": "Danish",
                    "delivery_address": "Batla House",
                    "delivery_time_raw": "kal 8 baje",
                    "takeaway_delivery_dine_in": "delivery",
                    "items": [
                        {
                            "name": "paneer tikka",
                            "quantity": 2,
                            "unit": "plate",
                            "spice_level": "less spicy",
                        }
                    ],
                },
                message,
                "inbound-menu-accept",
                {
                    "business_type": "restaurant",
                    "offerings": ["Paneer Tikka", "Veg Thali"],
                },
            )

        assert card["shop_id"] == "restaurant-shop"
        assert card["items"][0]["name"] == "Paneer Tikka"
        assert card["items"][0]["spice_level"] == "less spicy"

    def test_grocery_context_stays_backward_compatible_with_unmatched_item(self):
        message = NormalizedInboundMessage(
            shop_id="grocery-shop",
            customer_id="customer-1",
            channel="meta_whatsapp",
            provider_message_id="wamid-grocery-compat",
            message_type="text",
            raw_text="5 kilo aata kal 9 baje bhej dena",
        )
        unmatched = Item(
            name="aata",
            raw_name="aata",
            quantity=5,
            unit="kg",
            resolution_status="unmatched",
        )

        with (
            patch.object(
                IntentRouter,
                "_get_customer",
                return_value={
                    "name": "Danish",
                    "phone": "919000000000",
                    "default_address": "Batla House",
                },
            ),
            patch(
                "app.routes.endpoints._safe_items_from_extracted",
                return_value=[unmatched],
            ),
            patch(
                "app.services.time_parser.parse_delivery_time",
                return_value={
                    "normalized": "2026-08-03 9:00 PM",
                    "confidence": 0.95,
                    "warning": None,
                },
            ),
        ):
            card = IntentRouter._build_card_data(
                {
                    "customer_name": "Danish",
                    "delivery_address": "Batla House",
                    "delivery_time_raw": "kal 9 baje",
                    "items": [
                        {"name": "aata", "quantity": 5, "unit": "kg"}
                    ],
                },
                message,
                "inbound-grocery-compat",
                {"business_type": "grocery", "offerings": []},
            )

        assert card["items"][0]["name"] == "aata"


class TestRestaurantActionCardSchema:

    def test_item_supports_all_restaurant_fields(self):
        item = Item(
            name="paneer tikka",
            quantity=2,
            unit="plate",
            size_variant="half",
            add_ons=["extra cheese", "extra masala"],
            spice_level="less spicy",
            veg_non_veg="Veg",
        )
        assert item.name == "paneer tikka"
        assert item.quantity == 2
        assert item.size_variant == "half"
        assert item.add_ons == ["extra cheese", "extra masala"]
        assert item.spice_level == "less spicy"
        assert item.veg_non_veg == "Veg"

    def test_action_card_supports_restaurant_order_fields(self):
        card = ActionCard(
            id="test-1",
            source="text",
            transcript="Table 4 ke liye 3 cold coffee",
            takeaway_delivery_dine_in="Dine-in",
            table_number="4",
            special_instructions="extra sugar",
        )
        assert card.takeaway_delivery_dine_in == "Dine-in"
        assert card.table_number == "4"
        assert card.special_instructions == "extra sugar"

    def test_restaurant_item_with_add_ons_as_list(self):
        item = Item(
            name="pizza",
            quantity=1,
            size_variant="large",
            add_ons=["extra cheese", "extra paneer"],
        )
        assert isinstance(item.add_ons, list)
        assert item.add_ons == ["extra cheese", "extra paneer"]

    def test_restaurant_item_with_add_ons_empty_list(self):
        item = Item(
            name="dal makhani",
            quantity=1,
            add_ons=[],
            spice_level=None,
            veg_non_veg="Veg",
        )
        assert item.add_ons == []

    def test_restaurant_item_veg_non_veg_default(self):
        item = Item(name="chicken biryani", quantity=1)
        assert item.veg_non_veg is None


class TestRestaurantHindiOrders:

    @pytest.mark.parametrize("order_text,expected_name,expected_qty,expected_spice", [
        ("2 paneer tikka, ek less spicy", "paneer tikka", 2, "less spicy"),
        ("Kal 8 baje 20 veg thali deliver kar dena", "veg thali", 20, None),
        ("1 large pizza extra cheese, takeaway", "pizza", 1, None),
        ("Do plate chicken biryani medium spicy parcel", "chicken biryani", 2, "medium spicy"),
        ("3 cup cold coffee", "cold coffee", 3, None),
    ])
    def test_fallback_parser_extracts_restaurant_items(self, order_text, expected_name, expected_qty, expected_spice):
        result = GeminiService._parse_order_fallback(order_text)
        assert len(result["items"]) > 0
        item = next((i for i in result["items"] if expected_name in i["name"].lower()), None)
        assert item is not None, f"Item '{expected_name}' not found in {result['items']}"
        assert item["quantity"] == expected_qty
        assert item.get("spice_level") == expected_spice

    def test_fallback_parser_keeps_profile_fields_out_of_restaurant_items(self):
        result = GeminiService._parse_order_fallback(
            "2 plate chicken biryani medium spicy aur 1 paneer tikka less spicy. "
            "Naam Danish, address Batla House, kal 8 PM."
        )

        assert result["customer_name"] == "Danish"
        assert result["delivery_address"] == "Batla House"
        assert result["delivery_time"] == "kal 8 PM"
        assert result["items"] == [
            {
                "name": "chicken biryani",
                "quantity": 2,
                "unit": "plate",
                "price": None,
                "spice_level": "medium spicy",
            },
            {
                "name": "paneer tikka",
                "quantity": 1,
                "unit": "",
                "price": None,
                "spice_level": "less spicy",
            },
        ]

    def test_fallback_parser_extracts_delivery_time_for_restaurant(self):
        result = GeminiService._parse_order_fallback("Kal 8 baje 20 veg thali deliver kar dena")
        assert "kal" in result["delivery_time"].lower() or "8" in result["delivery_time"]


class TestGroceryConfigurationUnchanged:

    def test_grocery_required_fields_unchanged(self):
        config = get_business_default("grocery")
        assert config["required_order_fields"] == ["items"]

    def test_grocery_optional_fields_unchanged(self):
        config = get_business_default("grocery")
        expected = [
            "customer_name",
            "customer_phone",
            "delivery_address",
            "delivery_time",
            "payment_method",
        ]
        assert config["optional_order_fields"] == expected

    def test_grocery_terminology_unchanged(self):
        config = get_business_default("grocery")
        assert config["terminology"] == {
            "order": "order",
            "customer": "customer",
            "delivery": "delivery",
            "packer": "packer",
        }

    def test_grocery_default_unit_unchanged(self):
        config = get_business_default("grocery")
        assert config["extraction_context"]["default_unit"] == "piece"

    def test_grocery_allow_partial_quantities_unchanged(self):
        config = get_business_default("grocery")
        assert config["extraction_context"]["allow_partial_quantities"] is True

    def test_grocery_common_items_hint_unchanged(self):
        config = get_business_default("grocery")
        assert "atta" in config["extraction_context"]["common_items_hint"]
        assert "spices" in config["extraction_context"]["common_items_hint"]
