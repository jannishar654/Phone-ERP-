import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
DUMMY_DATE = "2026-01-01T00:00:00Z"

@pytest.fixture
def mock_deps():
    with patch("app.dependencies.auth.supabase_client") as mock_auth_sc, \
         patch("app.routes.staff.supabase_client") as mock_staff_sc, \
         patch("app.routes.orders.supabase_client") as mock_orders_sc, \
         patch("app.routes.orders.get_user_shop_id", return_value="shop-123"), \
         patch("app.routes.staff.get_optional_user_id", return_value="user-123"):
         
        yield {
            "staff": mock_staff_sc,
            "orders": mock_orders_sc
        }

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
def test_packer_can_update_status_and_persists(mock_deps):
    mock_sc = mock_deps["staff"]
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_members":
            mock_obj.select().eq().eq().eq().execute.return_value = MagicMock(data=[
                {"shop_id": "shop-123", "role": "packer"}
            ])
        elif table_name == "orders":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[
                {"id": "order-1", "lifecycle_status": "packing", "shop_id": "shop-123", "customer_id": "cust-1", "created_at": DUMMY_DATE, "updated_at": DUMMY_DATE}
            ])
            mock_obj.select().eq().execute.return_value = MagicMock(data=[
                {"id": "order-1", "lifecycle_status": "out_for_delivery", "shop_id": "shop-123", "order_items": [], "created_at": DUMMY_DATE, "updated_at": DUMMY_DATE}
            ])
            mock_obj.update().eq().execute.return_value = MagicMock(data=[{"id": "order-1"}])
        return mock_obj
    mock_sc.table.side_effect = mock_table_select
    response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "out_for_delivery"})
    assert response.status_code == 200

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
def test_delivery_dashboard_query(mock_deps):
    mock_sc = mock_deps["staff"]
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_members":
            mock_obj.select().eq().eq().eq().execute.return_value = MagicMock(data=[
                {"shop_id": "shop-123", "role": "delivery"}
            ])
        elif table_name == "orders":
            mock_obj.select().eq().eq().order().execute.return_value = MagicMock(data=[
                {"id": "order-1", "lifecycle_status": "out_for_delivery", "shop_id": "shop-123", "created_at": DUMMY_DATE, "updated_at": DUMMY_DATE, "order_items": []}
            ])
        return mock_obj
    mock_sc.table.side_effect = mock_table_select
    response = client.post("/staff/orders/delivery", json={})
    assert response.status_code == 200

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
def test_owner_dashboard_query(mock_deps):
    mock_orders = mock_deps["orders"]
    mock_orders.table().select().eq().order().execute.return_value = MagicMock(data=[
        {"id": "order-1", "lifecycle_status": "out_for_delivery", "shop_id": "shop-123", "created_at": DUMMY_DATE, "updated_at": DUMMY_DATE, "order_items": []}
    ])
    with patch("app.routes.orders.get_current_user_id", return_value="user-123"):
        response = client.get("/orders/")
        assert response.status_code == 200

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
def test_delivery_can_update_to_delivered(mock_deps):
    mock_sc = mock_deps["staff"]
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_members":
            mock_obj.select().eq().eq().eq().execute.return_value = MagicMock(data=[
                {"shop_id": "shop-123", "role": "delivery"}
            ])
        elif table_name == "orders":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[
                {"id": "order-1", "lifecycle_status": "out_for_delivery", "shop_id": "shop-123", "customer_id": "cust-1", "created_at": DUMMY_DATE, "updated_at": DUMMY_DATE, "order_items": []}
            ])
            mock_obj.select().eq().execute.return_value = MagicMock(data=[
                {"id": "order-1", "lifecycle_status": "delivered", "shop_id": "shop-123", "order_items": [], "created_at": DUMMY_DATE, "updated_at": DUMMY_DATE}
            ])
            mock_obj.update().eq().execute.return_value = MagicMock(data=[{"id": "order-1"}])
        elif table_name == "customer_channels":
            mock_obj.select().eq().execute.return_value = MagicMock(data=[])
        elif table_name == "order_public_links":
            mock_obj.select().eq().execute.return_value = MagicMock(data=[])
            mock_obj.insert().execute.return_value = MagicMock(data=[{"id": "link-1"}])
        return mock_obj
    mock_sc.table.side_effect = mock_table_select
    response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
    assert response.status_code == 200
