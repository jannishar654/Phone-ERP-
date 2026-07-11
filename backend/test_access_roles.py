import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
import hashlib

client = TestClient(app)

@pytest.fixture
def mock_supabase():
    with patch('app.routes.access.supabase_client') as mock_sc, \
         patch('app.routes.staff.supabase_client') as mock_staff_sc, \
         patch('app.routes.public.supabase_client') as mock_public_sc, \
         patch('app.routes.auth.supabase_client') as mock_auth_routes_sc, \
         patch('app.routes.invites.supabase_client') as mock_invites_sc, \
         patch('app.dependencies.auth.supabase_client') as mock_auth_sc, \
         patch('app.routes.access.get_user_shop_id') as mock_get_shop, \
         patch('app.routes.orders.get_user_shop_id') as mock_orders_shop, \
         patch('app.routes.catalog.supabase_client') as mock_cat_sc:
         
        mock_auth_sc.auth.get_user.return_value = MagicMock(user=MagicMock(id="user123"))
        mock_get_shop.return_value = "shop123"
        mock_orders_shop.return_value = "shop123"
        
        yield {
            "access": mock_sc,
            "staff": mock_staff_sc,
            "public": mock_public_sc,
            "auth": mock_auth_sc,
            "auth_routes": mock_auth_routes_sc,
            "invites": mock_invites_sc,
            "catalog": mock_cat_sc
        }

def test_owner_can_generate_access_token(mock_supabase):
    mock_sc = mock_supabase["access"]
    
    mock_insert = MagicMock()
    mock_insert.execute.return_value = MagicMock(data=[{
        "id": "access123",
        "shop_id": "shop123",
        "role": "packer",
        "label": "Packer 1",
        "expires_at": None,
        "revoked_at": None,
        "created_at": "2026-01-01T00:00:00Z"
    }])
    mock_sc.table().insert.return_value = mock_insert
    
    response = client.post("/access/staff", json={
        "shop_id": "shop123",
        "role": "packer",
        "label": "Packer 1"
    }, headers={"Authorization": "Bearer fake_token"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "packer"
    assert "raw_token" in data

def test_validate_staff_token(mock_supabase):
    mock_sc = mock_supabase["staff"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        mock_obj.select().eq().is_().execute.return_value = MagicMock(data=[{
            "id": "access123",
            "shop_id": "shop123",
            "role": "packer",
            "expires_at": None,
            "revoked_at": None
        }])
        return mock_obj
    mock_sc.table.side_effect = mock_table_select
    
    response = client.post("/staff/validate", json={"token": "some_token"})
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["role"] == "packer"

def test_packer_can_update_status_to_out_for_delivery(mock_supabase):
    mock_sc = mock_supabase["staff"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_staff_access":
            mock_obj.select().eq().is_().execute.return_value = MagicMock(data=[{"shop_id": "shop123", "role": "packer"}])
        elif table_name == "orders":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[{
                "id": "order123", "shop_id": "shop123", "lifecycle_status": "packing", "customer_id": "cust1",
                "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"
            }])
            mock_obj.select().eq().execute.return_value = MagicMock(data=[{
                "id": "order123", "shop_id": "shop123", "lifecycle_status": "out_for_delivery",
                "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"
            }])
            mock_obj.update().eq().execute.return_value = MagicMock(data=[{"id": "order123"}])
        return mock_obj
    mock_sc.table.side_effect = mock_table_select
    
    response = client.post("/staff/orders/order123/status", json={
        "token": "packer_token",
        "lifecycle_status": "out_for_delivery"
    })
    
    assert response.status_code == 200

def test_packer_cannot_mark_delivered(mock_supabase):
    mock_sc = mock_supabase["staff"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_staff_access":
            mock_obj.select().eq().is_().execute.return_value = MagicMock(data=[{"shop_id": "shop123", "role": "packer"}])
        return mock_obj
    mock_sc.table.side_effect = mock_table_select
    
    response = client.post("/staff/orders/order123/status", json={
        "token": "packer_token",
        "lifecycle_status": "delivered"
    })
    
    assert response.status_code == 403

def test_delivery_can_mark_delivered(mock_supabase):
    mock_sc = mock_supabase["staff"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_staff_access":
            mock_obj.select().eq().is_().execute.return_value = MagicMock(data=[{"shop_id": "shop123", "role": "delivery"}])
        elif table_name == "orders":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[{
                "id": "order123", "shop_id": "shop123", "lifecycle_status": "out_for_delivery", "customer_id": "cust1",
                "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"
            }])
            mock_obj.select().eq().execute.return_value = MagicMock(data=[{
                "id": "order123", "shop_id": "shop123", "lifecycle_status": "delivered", "customer_id": "cust1",
                "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"
            }])
            mock_obj.update().eq().execute.return_value = MagicMock(data=[{"id": "order123"}])
        elif table_name == "customer_channels":
            mock_obj.select().eq().execute.return_value = MagicMock(data=[])
        elif table_name == "order_public_links":
            mock_obj.select().eq().execute.return_value = MagicMock(data=[])
            mock_obj.insert().execute.return_value = MagicMock(data=[{"id": "123"}])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.post("/staff/orders/order123/status", json={
        "token": "delivery_token",
        "lifecycle_status": "delivered"
    })
    
    assert response.status_code == 200

def test_public_bill_link_read_only(mock_supabase):
    mock_sc = mock_supabase["public"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "order_public_links":
            # Return linked order 123
            mock_obj.select().eq().execute.return_value = MagicMock(data=[{"order_id": "order123", "shop_id": "shop123"}])
        elif table_name == "orders":
            mock_obj.select().eq().execute.return_value = MagicMock(data=[{
                "id": "order123", "shop_id": "shop123",
                "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"
            }])
        elif table_name == "shops":
            mock_obj.select().eq().execute.return_value = MagicMock(data=[{"id": "shop123", "name": "Test Shop"}])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.get("/public/bill/sometoken")
    assert response.status_code == 200
    data = response.json()
    assert "order_id" in data
    assert data["order_id"] == "order123"
    assert "shop_name" in data
    assert data["shop_name"] == "Test Shop"

def test_public_bill_rejects_missing_token(mock_supabase):
    mock_sc = mock_supabase["public"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "order_public_links":
            mock_obj.select().eq().execute.return_value = MagicMock(data=[])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.get("/public/bill/badtoken")
    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid bill link"

def test_public_bill_rejects_expired_token(mock_supabase):
    mock_sc = mock_supabase["public"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "order_public_links":
            mock_obj.select().eq().execute.return_value = MagicMock(data=[{
                "order_id": "order123", 
                "shop_id": "shop123",
                "expires_at": "2020-01-01T00:00:00Z"
            }])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.get("/public/bill/expiredtoken")
    assert response.status_code == 410
    assert response.json()["detail"] == "Bill link expired"


# --- NEW TESTS for Invites and Register Flow ---

def test_owner_can_generate_invite(mock_supabase):
    mock_sc = mock_supabase["invites"]
    
    with patch('app.routes.invites.get_user_shop_id', return_value="shop123"):
        mock_insert = MagicMock()
        mock_insert.execute.return_value = MagicMock(data=[{
            "id": "invite123",
            "shop_id": "shop123",
            "role": "packer",
            "label": "Packer Invite",
            "expires_at": None,
            "used_at": None,
            "revoked_at": None,
            "created_at": "2026-01-01T00:00:00Z"
        }])
        mock_sc.table().insert.return_value = mock_insert
        
        response = client.post("/invites/staff", json={
            "shop_id": "shop123",
            "role": "packer",
            "label": "Packer Invite"
        }, headers={"Authorization": "Bearer fake_token"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "packer"
        assert "raw_invite_code" in data

def test_staff_can_register_with_invite(mock_supabase):
    mock_sc = mock_supabase["auth_routes"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "staff_invites":
            mock_obj.select().eq().is_().is_().execute.return_value = MagicMock(data=[{
                "id": "invite123",
                "shop_id": "shop123",
                "role": "delivery",
                "expires_at": None
            }])
            mock_obj.update().eq().execute.return_value = MagicMock(data=[{"id": "invite123"}])
        elif table_name == "shop_members":
            mock_obj.select().eq().eq().eq().execute.return_value = MagicMock(data=[])
            mock_obj.insert().execute.return_value = MagicMock(data=[{"id": "member123"}])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.post("/auth/register-staff", json={
        "invite_code": "some_code"
    }, headers={"Authorization": "Bearer session_token"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["role"] == "delivery"

def test_expired_or_invalid_invite_rejected(mock_supabase):
    mock_sc = mock_supabase["auth_routes"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "staff_invites":
            mock_obj.select().eq().is_().is_().execute.return_value = MagicMock(data=[])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.post("/auth/register-staff", json={
        "invite_code": "some_code"
    }, headers={"Authorization": "Bearer session_token"})
    
    assert response.status_code == 400

def test_api_me_returns_owner_fallback(mock_supabase):
    mock_sc = mock_supabase["auth_routes"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_members":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[])
        elif table_name == "shops":
            mock_obj.select().eq().execute.return_value = MagicMock(data=[{"id": "shop123"}])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.get("/auth/me", headers={"Authorization": "Bearer session_token"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "owner"
    assert data["shop_id"] == "shop123"

def test_api_me_returns_staff_member(mock_supabase):
    mock_sc = mock_supabase["auth_routes"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_members":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[{
                "shop_id": "shop456",
                "role": "packer"
            }])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.get("/auth/me", headers={"Authorization": "Bearer session_token"})
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "packer"
    assert data["shop_id"] == "shop456"

@patch("app.config.settings.settings.REQUIRE_AUTH", True)
def test_packer_gets_403_on_catalog(mock_supabase):
    mock_sc = mock_supabase["catalog"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_members":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[{
                "shop_id": "shop123",
                "role": "packer"
            }])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.get("/catalog/", headers={"Authorization": "Bearer session_token"})
    assert response.status_code == 403
    assert "owner privileges" in response.json()["detail"]

@patch("app.config.settings.settings.REQUIRE_AUTH", True)
def test_delivery_gets_403_on_catalog(mock_supabase):
    mock_sc = mock_supabase["catalog"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_members":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[{
                "shop_id": "shop123",
                "role": "delivery"
            }])
        return mock_obj
        
    mock_sc.table.side_effect = mock_table_select
    
    response = client.get("/catalog/", headers={"Authorization": "Bearer session_token"})
    assert response.status_code == 403
    assert "owner privileges" in response.json()["detail"]

@patch("app.config.settings.settings.REQUIRE_AUTH", True)
def test_packer_cannot_access_action_cards(mock_supabase):
    mock_cat_sc = mock_supabase["catalog"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_members":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[{
                "shop_id": "shop123",
                "role": "packer"
            }])
        return mock_obj
        
    mock_cat_sc.table.side_effect = mock_table_select
    
    response = client.get("/action-cards", headers={"Authorization": "Bearer session_token"})
    assert response.status_code == 403
    assert "owner privileges" in response.json()["detail"]

@patch("app.config.settings.settings.REQUIRE_AUTH", True)
def test_delivery_cannot_mark_packing(mock_supabase):
    mock_sc = mock_supabase["staff"]
    
    def mock_table_select(table_name):
        mock_obj = MagicMock()
        if table_name == "shop_members":
            mock_obj.select().eq().eq().execute.return_value = MagicMock(data=[{
                "shop_id": "shop123",
                "role": "delivery"
            }])
        return mock_obj
    mock_sc.table.side_effect = mock_table_select
    
    response = client.post("/staff/orders/order123/status", json={
        "token": None,
        "lifecycle_status": "out_for_delivery"
    }, headers={"Authorization": "Bearer session_token"})
    
    assert response.status_code == 403
    assert "Delivery staff can only mark orders as delivered or cancelled" in response.json()["detail"]
