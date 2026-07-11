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
    def __init__(self, name, calls, mock_phone=None):
        self.name = name
        self.calls = calls
        self.mock_phone = mock_phone

    def select(self, *args, **kwargs):
        self.calls.append(("select", self.name, args, kwargs))
        if self.name == "orders":
            p = dict(ORDER_PAYLOAD)
            # If args contain 'order_items', return delivered (for final fetch)
            if args and "order_items" in args[0]:
                p["lifecycle_status"] = "delivered"
            return FakeQuery([p])
        if self.name == "customer_channels":
            channels = []
            if "telegram" not in self.calls:
                channels.append({"channel": "telegram", "channel_chat_id": "chat-1"})
            if "whatsapp" not in self.calls:
                channels.append({"channel": "whatsapp", "phone": self.mock_phone})
            return FakeQuery(channels)
        if self.name == "action_cards":
            return FakeQuery([{"source": "whatsapp", "customer_phone": "+919876543210"}])
        if self.name == "customers":
            return FakeQuery([{"phone": "+910000000000"}])
        if self.name == "order_public_links":
            if "mock_existing_link" in self.calls:
                return FakeQuery([{"id": "link-1", "order_id": "order-1"}])
            return FakeQuery([])
        return FakeQuery([])

    def update(self, *args, **kwargs):
        self.calls.append(("update", self.name, args, kwargs))
        if self.name == "orders":
            p = dict(ORDER_PAYLOAD)
            p.update(args[0])
            return FakeQuery([p])
        return FakeQuery([{"id": "test", **args[0]}])

    def insert(self, *args, **kwargs):
        self.calls.append(("insert", self.name, args, kwargs))
        return FakeQuery([{"id": "test"}])

class FakeSupabase:
    def __init__(self, mock_phone="9876543210"):
        self.calls = []
        self.mock_phone = mock_phone
        
    def table(self, name):
        return FakeTable(name, self.calls, self.mock_phone)

@pytest.fixture
def mock_deps():
    fake_db = FakeSupabase()
    with patch("app.dependencies.auth.supabase_client", fake_db), \
         patch("app.routes.staff.supabase_client", fake_db), \
         patch("app.routes.orders.supabase_client", fake_db), \
         patch("app.services.delivery_notification_service.supabase_client", fake_db), \
         patch("app.routes.staff.get_staff_context", return_value={"shop_id": "shop-123", "role": "delivery"}), \
         patch("app.routes.staff.get_optional_user_id", return_value="user-123"), \
         patch("app.routes.orders.get_user_shop_id", return_value="shop-123"), \
         patch("app.dependencies.auth.get_current_user_id", return_value="user-123"):
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
    original_select = FakeTable.select
    def mock_select(self, *args, **kwargs):
        if self.name == "action_cards":
            return FakeQuery([{"source": "telegram"}])
        return original_select(self, *args, **kwargs)
        
    with patch.object(FakeTable, 'select', mock_select):
        response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
        assert response.status_code == 200
        assert response.json()["notification_attempted"] is True
        assert response.json()["notification_sent"] is True
        assert response.json()["notification_channel"] == "telegram"
        
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        assert args[0] == "chat-1"
        assert "Your order has been delivered." in args[1]
        assert "Total: ₹500" in args[1]
        assert "Bill: http" in args[1]

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.twilio_whatsapp_service.twilio_whatsapp_service.send_whatsapp_message", return_value={"sent": True, "sid": "SM123", "status": "sent", "error": None})
def test_whatsapp_origin_sends_message(mock_send, mock_deps):
    response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
    assert response.status_code == 200
    resp_json = response.json()
    assert resp_json["notification_attempted"] is True
    assert resp_json["notification_sent"] is True
    assert resp_json["notification_channel"] == "whatsapp"
    assert resp_json["notification_sid"] == "SM123"
    
    mock_send.assert_called_once()
    args, _ = mock_send.call_args
    assert args[0] == "9876543210" # This is mock_phone passed into FakeSupabase

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.twilio_whatsapp_service.twilio_whatsapp_service.send_whatsapp_message", return_value={"sent": True, "sid": "SM123", "status": "sent", "error": None})
def test_whatsapp_order_only_customer_phone(mock_send):
    fake_db = FakeSupabase(mock_phone=None) # No channel phone
    with patch("app.dependencies.auth.supabase_client", fake_db), \
         patch("app.routes.staff.supabase_client", fake_db), \
         patch("app.routes.orders.supabase_client", fake_db), \
         patch("app.services.delivery_notification_service.supabase_client", fake_db), \
         patch("app.routes.staff.get_staff_context", return_value={"shop_id": "shop-123", "role": "delivery"}), \
         patch("app.routes.staff.get_optional_user_id", return_value="user-123"), \
         patch("app.routes.orders.get_user_shop_id", return_value="shop-123"), \
         patch("app.dependencies.auth.get_current_user_id", return_value="user-123"):
        
        response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
        assert response.status_code == 200
        resp_json = response.json()
        assert resp_json["notification_attempted"] is True
        assert resp_json["notification_sent"] is True
        assert resp_json["notification_channel"] == "whatsapp"
        
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        assert args[0] == "1234567890" # from order.customer_phone

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.twilio_whatsapp_service.twilio_whatsapp_service.send_whatsapp_message", return_value={"sent": False, "error": "Twilio API Error"})
def test_notification_failure_does_not_rollback_whatsapp(mock_send, mock_deps):
    response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
    assert response.status_code == 200
    resp_json = response.json()
    assert resp_json["lifecycle_status"] == "delivered"
    assert resp_json["notification_attempted"] is True
    assert resp_json["notification_sent"] is False
    assert resp_json["notification_error"] == "Twilio API Error"

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.telegram_service.telegram_service.send_message", side_effect=Exception("Telegram API Error"))
def test_telegram_failure_does_not_rollback(mock_send, mock_deps):
    original_select = FakeTable.select
    def mock_select(self, *args, **kwargs):
        if self.name == "action_cards":
            return FakeQuery([{"source": "telegram"}])
        return original_select(self, *args, **kwargs)
        
    with patch.object(FakeTable, 'select', mock_select):
        response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
        assert response.status_code == 200
        resp_json = response.json()
        assert resp_json["lifecycle_status"] == "delivered"
        assert resp_json["notification_attempted"] is True
        assert resp_json["notification_sent"] is False
        assert resp_json["notification_error"] == "Telegram API Error"

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
def test_whatsapp_missing_phone_does_not_rollback():
    fake_db = FakeSupabase(mock_phone=None)
    with patch("app.dependencies.auth.supabase_client", fake_db), \
         patch("app.routes.staff.supabase_client", fake_db), \
         patch("app.routes.orders.supabase_client", fake_db), \
         patch("app.services.delivery_notification_service.supabase_client", fake_db), \
         patch("app.routes.staff.get_staff_context", return_value={"shop_id": "shop-123", "role": "delivery"}), \
         patch("app.routes.staff.get_optional_user_id", return_value="user-123"), \
         patch("app.routes.orders.get_user_shop_id", return_value="shop-123"), \
         patch("app.dependencies.auth.get_current_user_id", return_value="user-123"):
        
        original_select = FakeTable.select
        def mock_select(self, *args, **kwargs):
            if self.name == "orders":
                p = dict(ORDER_PAYLOAD)
                p["customer_phone"] = None
                if args and "order_items" in args[0]:
                    p["lifecycle_status"] = "delivered"
                return FakeQuery([p])
            if self.name == "action_cards":
                return FakeQuery([{"source": "whatsapp", "customer_phone": None}])
            if self.name == "customers":
                return FakeQuery([{"phone": None}])
            return original_select(self, *args, **kwargs)
            
        original_update = FakeTable.update
        def mock_update(self, *args, **kwargs):
            if self.name == "orders":
                p = dict(ORDER_PAYLOAD)
                p["customer_phone"] = None
                p.update(args[0])
                return FakeQuery([p])
            return original_update(self, *args, **kwargs)
            
        with patch.object(FakeTable, 'select', mock_select), patch.object(FakeTable, 'update', mock_update):
            response = client.post("/staff/orders/order-1/status", json={"lifecycle_status": "delivered"})
            assert response.status_code == 200
            resp_json = response.json()
            assert resp_json["lifecycle_status"] == "delivered"
            assert resp_json["notification_attempted"] is True
            assert resp_json["notification_sent"] is False
            assert "No customer phone found" in resp_json.get("notification_error", "")

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

@patch("twilio.rest.Client")
def test_twilio_whatsapp_normalization(mock_client_class):
    from app.services.twilio_whatsapp_service import twilio_whatsapp_service
    from app.config.settings import settings
    settings.TWILIO_ACCOUNT_SID = "AC123"
    settings.TWILIO_AUTH_TOKEN = "token"
    settings.TWILIO_WHATSAPP_FROM = "+14155238886"
    
    mock_client_instance = mock_client_class.return_value
    mock_message = MagicMock()
    mock_message.sid = "SM123"
    mock_message.status = "queued"
    mock_client_instance.messages.create.return_value = mock_message
    
    res = twilio_whatsapp_service.send_whatsapp_message("9876543210", "Test")
    assert res["sent"] is True
    assert res["sid"] == "SM123"
    
    mock_client_instance.messages.create.assert_called_once_with(
        body="Test",
        from_="whatsapp:+14155238886",
        to="whatsapp:+919876543210"
    )


@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.twilio_whatsapp_service.twilio_whatsapp_service.send_whatsapp_message", return_value={"sent": True, "sid": "SM123", "status": "sent", "error": None})
def test_owner_marks_delivered_sends_whatsapp(mock_send, mock_deps):
    response = client.patch("/orders/order-1/status", json={"lifecycle_status": "delivered"})
    assert response.status_code == 200
    resp_json = response.json()
    assert resp_json["notification_attempted"] is True
    assert resp_json["notification_sent"] is True
    assert resp_json["notification_channel"] == "whatsapp"
    assert resp_json["notification_sid"] == "SM123"
    
    mock_send.assert_called_once()
    args, _ = mock_send.call_args
    assert args[0] == "9876543210"

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.telegram_service.telegram_service.send_message")
def test_owner_marks_delivered_sends_telegram(mock_send, mock_deps):
    original_select = FakeTable.select
    def mock_select(self, *args, **kwargs):
        if self.name == "action_cards":
            return FakeQuery([{"source": "telegram"}])
        return original_select(self, *args, **kwargs)
        
    with patch.object(FakeTable, 'select', mock_select):
        response = client.patch("/orders/order-1/status", json={"lifecycle_status": "delivered"})
        assert response.status_code == 200
        assert response.json()["notification_attempted"] is True
        assert response.json()["notification_sent"] is True
        assert response.json()["notification_channel"] == "telegram"
        mock_send.assert_called_once()

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.twilio_whatsapp_service.twilio_whatsapp_service.send_whatsapp_message", return_value={"sent": False, "error": "API Error"})
def test_owner_notification_failure_does_not_rollback(mock_send, mock_deps):
    response = client.patch("/orders/order-1/status", json={"lifecycle_status": "delivered"})
    assert response.status_code == 200
    resp_json = response.json()
    assert resp_json["lifecycle_status"] == "delivered"
    assert resp_json["notification_attempted"] is True
    assert resp_json["notification_sent"] is False

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.twilio_whatsapp_service.twilio_whatsapp_service.send_whatsapp_message")
def test_non_delivered_owner_status_update_does_not_send(mock_send, mock_deps):
    original_select = FakeTable.select
    def mock_select(self, *args, **kwargs):
        if self.name == "orders":
            p = dict(ORDER_PAYLOAD)
            p["lifecycle_status"] = "out_for_delivery" if (args and "order_items" in args[0]) else "packing"
            return FakeQuery([p])
        return original_select(self, *args, **kwargs)
        
    with patch.object(FakeTable, 'select', mock_select):
        response = client.patch("/orders/order-1/status", json={"lifecycle_status": "out_for_delivery"})
        assert response.status_code == 200
        assert response.json()["lifecycle_status"] == "out_for_delivery"
        assert response.json().get("notification_attempted") is None
        mock_send.assert_not_called()

@patch("app.config.settings.settings.REQUIRE_AUTH", False)
@patch("app.services.twilio_whatsapp_service.twilio_whatsapp_service.send_whatsapp_message")
def test_already_delivered_does_not_duplicate_send(mock_send, mock_deps):
    original_select = FakeTable.select
    def mock_select(self, *args, **kwargs):
        if self.name == "orders":
            p = dict(ORDER_PAYLOAD)
            p["lifecycle_status"] = "delivered"
            return FakeQuery([p])
        return original_select(self, *args, **kwargs)
        
    with patch.object(FakeTable, 'select', mock_select):
        response = client.patch("/orders/order-1/status", json={"lifecycle_status": "delivered"})
        assert response.status_code == 400
        assert "notification_attempted" not in response.json()
        mock_send.assert_not_called()
