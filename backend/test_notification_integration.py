import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

DUMMY_DATE = "2026-01-01T00:00:00Z"
ORDER_PAYLOAD = {
    "id": "order-1", 
    "action_card_id": "card-1", 
    "lifecycle_status": "out_for_delivery", 
    "shop_id": "shop-123", 
    "customer_id": "cust-1", 
    "total_amount": 500.0, 
    "created_at": DUMMY_DATE, 
    "updated_at": DUMMY_DATE, 
    "order_items": [],
    "customer_name": "Test",
    "customer_phone": "1234567890",
    "delivery_address": "Test Address",
    "payment_method": "cash",
    "order_number": 123
}

class FakeQuery:
    def __init__(self, data=None):
        self._data = data or []
    def eq(self, *args, **kwargs):
        return self
    def is_(self, *args, **kwargs):
        return self
    def order(self, *args, **kwargs):
        return self
    def execute(self):
        m = MagicMock()
        m.data = self._data
        return m

class FakeTable:
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls

    def select(self, *args, **kwargs):
        self.calls.append(("select", self.name, args, kwargs))
        if self.name == "orders":
            p = dict(ORDER_PAYLOAD)
            # If args contain 'order_items', return delivered (for final fetch)
            if args and "order_items" in args[0]:
                p["lifecycle_status"] = "delivered"
            return FakeQuery([p])
        if self.name == "customer_channels":
            return FakeQuery([{"channel": "telegram", "channel_chat_id": "chat-1"}, {"channel": "whatsapp", "channel_phone_number": "+1234567890"}])
        if self.name == "action_cards":
            return FakeQuery([{"source": "telegram"}])
        if self.name == "order_public_links":
            # For update test, return existing
            if "mock_existing_link" in self.calls:
                return FakeQuery([{"id": "link-1", "order_id": "order-1"}])
            return FakeQuery([])
        return FakeQuery([])

    def update(self, *args, **kwargs):
        self.calls.append(("update", self.name, args, kwargs))
        return FakeQuery([{"id": "test"}])

    def insert(self, *args, **kwargs):
        self.calls.append(("insert", self.name, args, kwargs))
        return FakeQuery([{"id": "test"}])

class FakeSupabase:
    def __init__(self):
        self.calls = []
        
    def table(self, name):
        return FakeTable(name, self.calls)

@pytest.fixture
def mock_deps():
    fake_db = FakeSupabase()
    with patch("app.dependencies.auth.supabase_client", fake_db), \
         patch("app.routes.staff.supabase_client", fake_db), \
         patch("app.routes.staff.get_staff_context", return_value={"shop_id": "shop-123", "role": "delivery"}), \
         patch("app.routes.staff.get_optional_user_id", return_value="user-123"):
        yield fake_db

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
def test_delivery_marks_delivered_creates_bill_link(mock_deps):
    response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
    assert response.status_code == 200
    
    inserts = [c for c in mock_deps.calls if c[0] == "insert" and c[1] == "order_public_links"]
    assert len(inserts) == 1
    assert inserts[0][2][0]["order_id"] == "order-1"
    assert "token_hash" in inserts[0][2][0]

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.telegram_service.telegram_service.send_message")
def test_telegram_origin_sends_message(mock_send, mock_deps):
    response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
    assert response.status_code == 200
    
    mock_send.assert_called_once()
    args, _ = mock_send.call_args
    assert args[0] == "chat-1"
    assert "Your order has been delivered." in args[1]
    assert "Total: ₹500" in args[1]
    assert "Bill: http" in args[1]

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.twilio_whatsapp_service.twilio_whatsapp_service.send_message")
def test_whatsapp_origin_sends_message(mock_send, mock_deps):
    # Mock action_cards to return source=whatsapp
    original_select = FakeTable.select
    def mock_select(self, *args, **kwargs):
        if self.name == "action_cards":
            return FakeQuery([{"source": "whatsapp"}])
        return original_select(self, *args, **kwargs)
        
    with patch.object(FakeTable, 'select', mock_select):
        response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
        assert response.status_code == 200
        
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        assert args[0] == "+1234567890"

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.telegram_service.telegram_service.send_message", side_effect=Exception("Network Error"))
def test_notification_failure_does_not_rollback(mock_send, mock_deps):
    response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
    assert response.status_code == 200
    assert response.json()["lifecycle_status"] == "delivered"

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
def test_existing_bill_link_updates_instead_of_duplicate(mock_deps):
    mock_deps.calls.append("mock_existing_link")
    response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
    assert response.status_code == 200
    
    updates = [c for c in mock_deps.calls if c[0] == "update" and c[1] == "order_public_links"]
    assert len(updates) == 1
    inserts = [c for c in mock_deps.calls if c[0] == "insert" and c[1] == "order_public_links"]
    assert len(inserts) == 0

def test_token_hashing():
    from app.utils.security import generate_deterministic_bill_token, hash_token
    token = generate_deterministic_bill_token("order-1", "shop-123")
    assert token is not None
    assert len(token) > 20
    
    h = hash_token(token)
    assert h != token
    assert len(h) == 64
