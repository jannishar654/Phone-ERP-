import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add backend dir to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.services.matching_service import matching_service
from app.services.order_service import order_service
from app.services.catalog_service import catalog_service
from app.schemas.catalog import CatalogItemCreate
import app.routes.catalog as catalog_routes

class TestCatalogMatchingAndOrder(unittest.TestCase):
    
    def test_catalog_service_mock_mode(self):
        # Temporarily mock out supabase
        old_supabase = catalog_service.supabase
        old_route_supabase = catalog_routes.supabase_client
        catalog_service.supabase = None
        catalog_routes.supabase_client = None
        
        try:
            # Test route shop mock
            mock_shop = catalog_routes.get_user_shop_id("test_user")
            self.assertEqual(mock_shop, "mock-shop")

            # Clear mock db
            catalog_service.mock_db = []
            
            # Create
            item_data = CatalogItemCreate(
                shop_id="mock-shop",
                canonical_name="sugar",
                display_name="Sugar",
                base_price=45.0,
                unit="kg",
                aliases=["chini"]
            )
            created = catalog_service.create_item(item_data)
            self.assertIsNotNone(created)
            self.assertEqual(created["shop_id"], "mock-shop")
            self.assertEqual(created["canonical_name"], "sugar")
            
            # Create Action Card
            from app.services.store import store
            card_data = {
                "id": "mock_card_123",
                "customer_name": "Danish",
                "shop_id": "mock-shop",
                "items": [
                    {"name": "chini", "quantity": 5, "unit": "kg", "price": 0.0, "price_status": "Pending Price Verification"}
                ],
                "status": "pending"
            }
            store.create(card_data)

            # Convert to Order
            from app.services.order_service import order_service
            old_order_supabase = order_service.supabase
            order_service.supabase = None
            
            try:
                order = order_service.convert_action_card_to_order("mock_card_123", "test_user")
                self.assertIsNotNone(order)
                self.assertEqual(order["status"], "pending")
                self.assertEqual(order["total_amount"], 225.0)
                self.assertEqual(len(order["order_items"]), 1)
                
                oi = order["order_items"][0]
                self.assertEqual(oi["unit_price"], 45.0)
                self.assertEqual(oi["line_total"], 225.0)
                
                # Check store status
                updated_card = store.get_by_id("mock_card_123")
                self.assertEqual(updated_card.status, "converted")
            finally:
                order_service.supabase = old_order_supabase

        finally:
            catalog_service.supabase = old_supabase
            catalog_routes.supabase_client = old_route_supabase

    @patch.object(catalog_service, "get_items_by_shop")
    def test_catalog_item_price_match(self, mock_get_items):
        # Mock catalog items response
        mock_get_items.return_value = [
            {"id": "item1", "canonical_name": "surf excel", "display_name": "Surf Excel Easy Wash", "base_price": 50.0, "unit": "packet", "aliases": ["lal surf"]},
            {"id": "item2", "canonical_name": "Aashirvaad Atta", "display_name": "Aashirvaad Atta", "base_price": 40.0, "unit": "kg", "aliases": ["aata", "atta"]}
        ]
        
        # Test exact match
        res = matching_service.match_product("surf excel", "shop1")
        self.assertEqual(res["resolution_status"], "matched")
        self.assertEqual(res["unit_price"], 50.0)
        
        # Test alias match
        res = matching_service.match_product("lal surf", "shop1")
        self.assertEqual(res["resolution_status"], "matched")
        self.assertEqual(res["unit_price"], 50.0)

        # Test aata alias match
        res = matching_service.match_product("aata", "shop1")
        self.assertEqual(res["resolution_status"], "matched")
        self.assertEqual(res["unit_price"], 40.0)
        self.assertEqual(res["canonical_name"], "Aashirvaad Atta")
        self.assertEqual(res["display_name"], "Aashirvaad Atta")

    @patch.object(catalog_service, "get_items_by_shop")
    def test_alias_mapping_display_names(self, mock_get_items):
        mock_get_items.return_value = [
            {"id": "sugar_id", "canonical_name": "sugar", "display_name": "Sugar / Chini", "base_price": 45.0, "unit": "kg", "aliases": ["chini", "cheeni"]},
            {"id": "atta_id", "canonical_name": "atta", "display_name": "Aashirvaad Atta", "base_price": 45.0, "unit": "kg", "aliases": ["aata"]},
            {"id": "oil_id", "canonical_name": "oil", "display_name": "Oil", "base_price": 170.0, "unit": "ltr", "aliases": ["tail"]}
        ]
        
        # Test sugar aliases
        for raw in ["chini", "cheeni", "sugar"]:
            res = matching_service.match_product(raw, "shop_abc")
            self.assertEqual(res["resolution_status"], "matched")
            self.assertEqual(res["display_name"], "Sugar / Chini")
            self.assertEqual(res["raw_name"], raw)
            self.assertEqual(res["unit_price"], 45.0)

        # Test atta aliases
        for raw in ["aata", "atta"]:
            res = matching_service.match_product(raw, "shop_abc")
            self.assertEqual(res["resolution_status"], "matched")
            self.assertEqual(res["display_name"], "Aashirvaad Atta")
            self.assertEqual(res["raw_name"], raw)
            self.assertEqual(res["unit_price"], 45.0)

        # Test oil aliases
        for raw in ["tail", "oil"]:
            res = matching_service.match_product(raw, "shop_abc")
            self.assertEqual(res["resolution_status"], "matched")
            self.assertEqual(res["display_name"], "Oil")
            self.assertEqual(res["raw_name"], raw)
            self.assertEqual(res["unit_price"], 170.0)

    @patch.object(catalog_service, "get_items_by_shop")
    def test_unmatched_product_returns_review_required(self, mock_get_items):
        mock_get_items.return_value = [
            {"id": "item1", "canonical_name": "surf excel", "display_name": "Surf Excel Easy Wash", "base_price": 50.0, "unit": "packet", "aliases": []}
        ]
        
        # Test unmatched
        res = matching_service.match_product("unknown item 123", "shop1")
        self.assertEqual(res["resolution_status"], "unmatched")
        self.assertEqual(res["unit_price"], 0.0)

    @patch.object(catalog_service, "get_items_by_shop")
    def test_ambiguous_product_does_not_auto_match(self, mock_get_items):
        # Create similar items to force ambiguity
        mock_get_items.return_value = [
            {"id": "item1", "canonical_name": "surf excel 1kg", "display_name": "Surf Excel 1kg", "base_price": 100.0, "aliases": []},
            {"id": "item2", "canonical_name": "surf excel 2kg", "display_name": "Surf Excel 2kg", "base_price": 200.0, "aliases": []}
        ]
        
        # Test ambiguous
        res = matching_service.match_product("surf excel", "shop1")
        self.assertEqual(res["resolution_status"], "ambiguous")
        self.assertIn("Surf Excel 1kg", res["possible_matches"])
        self.assertIn("Surf Excel 2kg", res["possible_matches"])
        self.assertEqual(res["unit_price"], 0.0)

    @patch.object(order_service, "supabase")
    def test_action_card_converts_to_order(self, mock_supabase):
        # Mock fetch action card
        mock_card_res = MagicMock()
        mock_card_res.data = [{
            "id": "card1",
            "shop_id": "shop1",
            "customer_id": "cust1",
            "items": [{"name": "surf", "quantity": 2, "price": 50.0, "price_status": "matched", "unit": "packet"}]
        }]
        
        # Mock insert order
        mock_order_res = MagicMock()
        mock_order_res.data = [{"id": "order1"}]
        
        # Mock complete order fetch
        mock_final_res = MagicMock()
        mock_final_res.data = [{"id": "order1", "total_amount": 100.0, "status": "pending"}]
        
        mock_supabase.table().select().eq().execute.side_effect = [mock_card_res, mock_final_res]
        mock_supabase.table().insert().execute.return_value = mock_order_res
        
        res = order_service.convert_action_card_to_order("card1", "user1")
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], "order1")

    @patch.object(order_service, "supabase")
    @patch.object(matching_service, "match_product")
    def test_order_item_preserves_display_name_and_raw_name(self, mock_match, mock_supabase):
        mock_match.return_value = {
            "resolution_status": "matched",
            "catalog_item_id": "atta_id",
            "canonical_name": "atta",
            "display_name": "Aashirvaad Atta",
            "unit": "kg",
            "unit_price": 45.0
        }
        
        mock_card_res = MagicMock()
        mock_card_res.data = [{
            "id": "card1",
            "shop_id": "shop1",
            "items": [{"name": "Aashirvaad Atta", "raw_name": "aata", "quantity": 1}]
        }]
        mock_order_res = MagicMock()
        mock_order_res.data = [{"id": "order1"}]
        mock_item_res = MagicMock()
        mock_item_res.data = [{"id": "item1"}]
        mock_final_res = MagicMock()
        mock_final_res.data = [{"id": "order1", "total_amount": 45.0, "status": "pending"}]
        
        # side_effect for select: 1 for action card, 1 for final order
        mock_supabase.table().select().eq().execute.side_effect = [mock_card_res, mock_final_res]
        
        # insert side effects: order, order_items
        mock_supabase.table().insert().execute.side_effect = [mock_order_res, mock_item_res]
        
        # capture the items insert payload
        mock_insert = mock_supabase.table().insert
        
        res = order_service.convert_action_card_to_order("card1", "user1")
        self.assertIsNotNone(res)
        
        # find the insert call for items (which is a list)
        items_payload = None
        for call in mock_insert.call_args_list:
            args = call[0]
            if args and isinstance(args[0], list):
                items_payload = args[0]
                break
                
        self.assertIsNotNone(items_payload)
        self.assertEqual(len(items_payload), 1)
        self.assertEqual(items_payload[0]["raw_name"], "aata")
        self.assertEqual(items_payload[0]["display_name"], "Aashirvaad Atta")

    @patch.object(order_service, "supabase")
    def test_price_missing_keeps_pending_price_verification(self, mock_supabase):
        mock_card_res = MagicMock()
        mock_card_res.data = [{
            "id": "card1",
            "shop_id": "shop1",
            "items": [{"name": "surf", "quantity": 2, "price": 0.0, "price_status": "Pending Price Verification"}]
        }]
        mock_order_res = MagicMock()
        mock_order_res.data = [{"id": "order1"}]
        mock_final_res = MagicMock()
        mock_final_res.data = [{"id": "order1", "total_amount": 0.0, "status": "Pending Price Verification"}]
        
        mock_supabase.table().select().eq().execute.side_effect = [mock_card_res, mock_final_res]
        mock_supabase.table().insert().execute.return_value = mock_order_res
        
        res = order_service.convert_action_card_to_order("card1", "user1")
        self.assertEqual(res["status"], "Pending Price Verification")

    @patch.object(order_service, "supabase")
    def test_old_action_card_without_shop_id_does_not_crash(self, mock_supabase):
        mock_card_res = MagicMock()
        # No shop_id provided
        mock_card_res.data = [{
            "id": "card1",
            "items": [{"name": "surf", "quantity": 2, "price": 50.0}]
        }]
        mock_order_res = MagicMock()
        mock_order_res.data = [{"id": "order1"}]
        mock_final_res = MagicMock()
        mock_final_res.data = [{"id": "order1", "total_amount": 100.0, "status": "pending"}]
        
        mock_supabase.table().select().eq().execute.side_effect = [mock_card_res, mock_final_res]
        mock_supabase.table().insert().execute.return_value = mock_order_res
        
        try:
            res = order_service.convert_action_card_to_order("card1", "user1")
            self.assertIsNotNone(res)
        except Exception as e:
            self.fail(f"Conversion crashed with exception: {e}")

    @patch("app.routes.catalog.supabase_client")
    @patch("app.config.settings.settings.REQUIRE_AUTH", False)
    def test_get_user_shop_id_auth_disabled_none_user(self, mock_supabase):
        from app.routes.catalog import get_user_shop_id
        
        mock_res = MagicMock()
        mock_res.data = [{"id": "shop_123"}]
        mock_supabase.table().select().is_().execute.return_value = mock_res
        
        # When user_id is None and auth is False, it should use the demo shop where owner_id IS NULL
        shop_id = get_user_shop_id(None)
        self.assertEqual(shop_id, "shop_123")
        
        # Verify Supabase was called to check owner_id IS NULL
        mock_supabase.table().select().is_.assert_called_with("owner_id", "null")

    @patch("app.routes.catalog.supabase_client")
    @patch("app.config.settings.settings.REQUIRE_AUTH", True)
    def test_get_user_shop_id_auth_enabled_none_user(self, mock_supabase):
        from app.routes.catalog import get_user_shop_id
        from fastapi import HTTPException
        
        # When user_id is None and auth is True, it should raise 401
        with self.assertRaises(HTTPException) as context:
            get_user_shop_id(None)
        
        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Authentication required")
        # Ensure Supabase wasn't queried
        mock_supabase.table().select().eq.assert_not_called()
        mock_supabase.table().select().is_.assert_not_called()

    @patch("app.routes.catalog.supabase_client")
    @patch("app.config.settings.settings.REQUIRE_AUTH", True)
    def test_get_user_shop_id_auth_enabled_valid_user(self, mock_supabase):
        from app.routes.catalog import get_user_shop_id
        
        mock_res = MagicMock()
        mock_res.data = [{"id": "shop_456"}]
        mock_supabase.table().select().eq().execute.return_value = mock_res
        
        shop_id = get_user_shop_id("user_123")
        self.assertEqual(shop_id, "shop_456")
        
        mock_supabase.table().select().eq.assert_called_with("owner_id", "user_123")

if __name__ == '__main__':
    unittest.main()
