from unittest.mock import MagicMock, patch

import pytest

from app.config.business_defaults import (
    BUSINESS_DEFAULTS,
    CANONICAL_WORKFLOW_STAGES,
    get_business_default,
)
from app.schemas.action_card import ActionCard, Item
from app.schemas.business_config import BusinessType
from app.services.business_config_service import BusinessConfigService
from app.services.gemini import GeminiService


def make_query(data=None):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.insert.return_value = query
    query.execute.return_value = MagicMock(data=data or [])
    return query


class TestRestaurantDefaults:

    def test_restaurant_has_all_required_fields(self):
        config = get_business_default("restaurant")
        expected = {
            "items", "quantity", "size_variant",
            "add_ons", "spice_level", "veg_non_veg",
        }
        assert set(config["required_order_fields"]) == expected

    def test_restaurant_has_all_optional_fields(self):
        config = get_business_default("restaurant")
        expected = {
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
        assert "size_variant" in context["required_order_fields"]
        assert "add_ons" in context["required_order_fields"]
        assert "spice_level" in context["required_order_fields"]
        assert "veg_non_veg" in context["required_order_fields"]

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
        assert "size_variant" in context["required_order_fields"]
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
