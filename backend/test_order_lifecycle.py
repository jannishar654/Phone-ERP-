import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.order import OrderLifecycleUpdate
from app.services.order_service import order_service

client = TestClient(app)

@pytest.fixture
def mock_supabase():
    with patch("app.routes.orders.supabase_client") as mock:
        yield mock

@pytest.fixture
def mock_supabase_service():
    with patch("app.services.order_service.supabase_client") as mock:
        yield mock

@pytest.fixture
def mock_auth():
    with patch("app.routes.orders.get_current_user_id", return_value="user_123"):
        with patch("app.routes.orders.get_user_shop_id", return_value="shop_123"):
            yield

def test_convert_action_card_creates_packing_status(mock_supabase_service):
    # Setup mock action card
    mock_action_card = {
        "id": "ac_123",
        "shop_id": "shop_123",
        "customer_id": "cust_123",
        "items": [{"name": "Item 1", "price": 10.0, "quantity": 2}],
        "delivery_address": "Home",
        "payment_method": "Cash"
    }
    
    mock_supabase_service.table().select().eq().execute.return_value.data = [mock_action_card]
    
    # Mock matching service
    with patch("app.services.matching_service.matching_service.match_product") as mock_match:
        mock_match.return_value = {"resolution_status": "matched", "unit_price": 10.0, "catalog_item_id": "cat_1"}
        
        # Mock order insertion
        mock_supabase_service.table().insert().execute.return_value.data = [{"id": "order_123"}]
        mock_supabase_service.table().select().eq().execute.return_value.data = [{"id": "order_123", "shop_id": "shop_123", "lifecycle_status": "packing", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00", "order_items": []}]
        
        order_service.supabase = mock_supabase_service
        order = order_service.convert_action_card_to_order("ac_123", "user_123")
        
        # Verify that insert was called with lifecycle_status = "packing"
        insert_calls = mock_supabase_service.table.return_value.insert.call_args_list
        inserted_order_data = None
        for call in insert_calls:
            if call.args:
                data = call.args[0]
            else:
                data = call.kwargs.get("json", {}) or call.kwargs.get("data", {})
            if isinstance(data, dict) and "total_amount" in data:
                inserted_order_data = data
                break
                
        assert inserted_order_data is not None, "Order insert call not found"
        assert inserted_order_data["lifecycle_status"] == "packing"
        assert order["lifecycle_status"] == "packing"

def test_valid_transition_packing_to_out_for_delivery(mock_auth, mock_supabase):
    # Setup initial state
    mock_supabase.table().select().eq().eq().execute.return_value.data = [{"id": "order_1", "shop_id": "shop_123", "lifecycle_status": "packing", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00"}]
    mock_supabase.table().update().eq().execute.return_value.data = [{"id": "order_1"}]
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "order_1", "shop_id": "shop_123", "lifecycle_status": "out_for_delivery", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00", "order_items": []}]
    
    response = client.patch(
        "/orders/order_1/status",
        json={"lifecycle_status": "out_for_delivery"}
    )
    
    assert response.status_code == 200
    assert response.json()["lifecycle_status"] == "out_for_delivery"
    # Verify timestamp was set
    update_call = mock_supabase.table().update.call_args[0][0]
    assert "out_for_delivery_at" in update_call
    assert update_call["lifecycle_status"] == "out_for_delivery"

def test_invalid_transition_rejected(mock_auth, mock_supabase):
    mock_supabase.table().select().eq().eq().execute.return_value.data = [{"id": "order_1", "shop_id": "shop_123", "lifecycle_status": "out_for_delivery"}]
    
    response = client.patch(
        "/orders/order_1/status",
        json={"lifecycle_status": "packing"}
    )
    
    assert response.status_code == 400
    assert "Invalid transition" in response.json()["detail"]

def test_cancelled_flow(mock_auth, mock_supabase):
    mock_supabase.table().select().eq().eq().execute.return_value.data = [{"id": "order_1", "shop_id": "shop_123", "lifecycle_status": "pending_review", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00"}]
    mock_supabase.table().update().eq().execute.return_value.data = [{"id": "order_1"}]
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "order_1", "shop_id": "shop_123", "lifecycle_status": "cancelled", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00", "order_items": []}]
    
    response = client.patch(
        "/orders/order_1/status",
        json={"lifecycle_status": "cancelled"}
    )
    
    assert response.status_code == 200
    assert response.json()["lifecycle_status"] == "cancelled"
    update_call = mock_supabase.table().update.call_args[0][0]
    assert "cancelled_at" in update_call

def test_old_null_lifecycle_orders_fallback(mock_auth, mock_supabase):
    # DB returns None for lifecycle_status
    mock_supabase.table().select().eq().eq().execute.return_value.data = [{"id": "order_old", "shop_id": "shop_123", "lifecycle_status": None, "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00"}]
    mock_supabase.table().update().eq().execute.return_value.data = [{"id": "order_old"}]
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "order_old", "shop_id": "shop_123", "lifecycle_status": "packing", "created_at": "2023-01-01T00:00:00", "updated_at": "2023-01-01T00:00:00", "order_items": []}]
    
    response = client.patch(
        "/orders/order_old/status",
        json={"lifecycle_status": "packing"}
    )
    
    assert response.status_code == 200
    update_call = mock_supabase.table().update.call_args[0][0]
    assert update_call["lifecycle_status"] == "packing"
    assert "packed_at" in update_call

def test_shop_isolation(mock_auth, mock_supabase):
    # If order belongs to another shop, it won't be found
    mock_supabase.table().select().eq().eq().execute.return_value.data = []
    
    response = client.patch(
        "/orders/order_other_shop/status",
        json={"lifecycle_status": "packing"}
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_mock_order_number_sequence_persistence():
    import os
    import json
    from app.services.order_service import OrderService
    
    # Ensure any existing sequence file is cleared or mocked
    seq_file = os.path.join(os.path.dirname(__file__), "app", "data", "sequence.json")
    original_content = None
    if os.path.exists(seq_file):
        try:
            with open(seq_file, "r") as f:
                original_content = f.read()
            os.remove(seq_file)
        except Exception:
            pass
            
    try:
        service = OrderService()
        service.supabase = None # enforce mock mode
        
        # We need mock action card and matching mock
        mock_action_card = {
            "id": "ac_mock_seq",
            "shop_id": "shop_123",
            "customer_id": "cust_123",
            "items": [{"name": "Item 1", "price": 10.0, "quantity": 2}],
            "delivery_address": "Home",
            "payment_method": "Cash"
        }
        
        with patch("app.services.store.store.get_by_id", return_value=MagicMock(model_dump=lambda: mock_action_card)):
            with patch("app.services.store.store.update_status") as mock_update_status:
                with patch("app.services.matching_service.matching_service.match_product", return_value={"resolution_status": "matched", "unit_price": 10.0}):
                    # First conversion
                    order1 = service.convert_action_card_to_order("ac_mock_seq", "user_123")
                    assert order1["order_number"] == 1001
                    
                    # Second conversion (sequence increments)
                    order2 = service.convert_action_card_to_order("ac_mock_seq", "user_123")
                    assert order2["order_number"] == 1002
                    
                    # Check sequence file content
                    assert os.path.exists(seq_file)
                    with open(seq_file, "r") as f:
                        data = json.load(f)
                        assert data["order_number_seq"] == 1003
                        
                    # Re-instantiate order service to simulate server restart
                    service_new = OrderService()
                    service_new.supabase = None
                    order3 = service_new.convert_action_card_to_order("ac_mock_seq", "user_123")
                    assert order3["order_number"] == 1003
    finally:
        # Restore original sequence file
        if os.path.exists(seq_file):
            try:
                os.remove(seq_file)
            except Exception:
                pass
        if original_content is not None:
            try:
                with open(seq_file, "w") as f:
                    f.write(original_content)
            except Exception:
                pass

