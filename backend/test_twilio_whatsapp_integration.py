import pytest
import os
import time
from unittest.mock import patch, MagicMock

# We need to set these before loading the module to avoid connection errors if they try to init on load
os.environ["TWILIO_AUTH_TOKEN"] = "testtoken"
os.environ["TWILIO_ACCOUNT_SID"] = "testaccount"
os.environ["TWILIO_DEFAULT_OWNER_ID"] = "4f4ea61e-3f37-4e90-9a47-0c98fe2036e1"
os.environ["TWILIO_DEFAULT_SHOP_ID"] = "44b5785d-a428-492e-a109-02b417d3ac59"
os.environ["SUPABASE_URL"] = "http://localhost:8000"
os.environ["SUPABASE_KEY"] = "fake-key"
os.environ["ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

@pytest.fixture(autouse=True)
def mock_supabase():
    with patch("app.services.supabase.supabase_client") as mock:
        yield mock

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)

def test_twilio_signature_validation(client):
    """Test that a missing or invalid signature is rejected"""
    payload = {"Body": "hi"}
    response = client.post("/twilio/whatsapp/webhook", data=payload)
    assert response.status_code == 403
    assert response.json() == {"detail": "Missing Twilio signature"}
    
    response = client.post("/twilio/whatsapp/webhook", data=payload, headers={"X-Twilio-Signature": "wrong"})
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid signature"}

@patch("app.services.twilio_whatsapp_service.TwilioWhatsappService.process_update")
def test_twilio_signature_valid(mock_process, client):
    """Test that a valid signature passes"""
    mock_process.return_value = "<Response><Message>ok</Message></Response>"
    payload = {"Body": "hi"}
    
    validator = RequestValidator("testtoken")
    url = "http://testserver/twilio/whatsapp/webhook"
    sig = validator.compute_signature(url, payload)
    
    response = client.post("/twilio/whatsapp/webhook", data=payload, headers={"X-Twilio-Signature": sig})
    assert response.status_code == 200
    assert "<Response><Message>ok</Message></Response>" in response.text
    mock_process.assert_called_once()

@patch("app.services.twilio_whatsapp_service.supabase_client")
@pytest.mark.asyncio
async def test_twilio_onboarding_flow(mock_supa):
    """Test the onboarding state machine"""
    from app.services.twilio_whatsapp_service import twilio_whatsapp_service
    
    # Mock shop config is correct
    
    # Mock customer doesn't exist yet, then created
    # Setup chain for get_or_create_customer
    mock_chan_select = MagicMock()
    mock_chan_select.eq().eq().eq().execute.return_value = MagicMock(data=[])
    
    mock_cust_select = MagicMock()
    mock_cust_select.eq().eq().execute.return_value = MagicMock(data=[])
    
    def mock_table(t):
        mock_t = MagicMock()
        if t == "customer_channels":
            mock_t.select.return_value = mock_chan_select
        else:
            mock_t.select.return_value = mock_cust_select
            
        mock_t.insert.side_effect = lambda data: mock_cust_insert if "name" in data else mock_chan_insert
        return mock_t

    mock_supa.table.side_effect = mock_table
    
    mock_cust_insert = MagicMock()
    mock_cust_insert.execute.return_value = MagicMock(data=[{"id": "cust-1"}])
    mock_chan_insert = MagicMock()
    mock_chan_insert.execute.return_value = MagicMock(data=[{
        "id": "chan-1",
        "state": "awaiting_name",
        "profile_completed": False
    }])
    
    # Send /start
    res = await twilio_whatsapp_service.process_update({"Body": "/start", "From": "whatsapp:+919999999999", "WaId": "919999999999"})
    assert "Welcome to PhoneERP. Please tell me your name." in res
    
    # Now simulate they replied with name
    mock_chan_select.eq().eq().eq().execute.return_value = MagicMock(data=[{
        "id": "chan-1", "state": "awaiting_name", "profile_completed": False,
        "customers": {"id": "cust-1", "name": "Unknown"}
    }])
    res = await twilio_whatsapp_service.process_update({"Body": "John Doe", "From": "whatsapp:+919999999999", "WaId": "919999999999"})
    assert "Thanks! What is your delivery address?" in res
    
    # Address
    mock_chan_select.eq().eq().eq().execute.return_value = MagicMock(data=[{
        "id": "chan-1", "state": "awaiting_address", "profile_completed": False,
        "customers": {"id": "cust-1", "name": "John Doe"}
    }])
    res = await twilio_whatsapp_service.process_update({"Body": "123 Main St", "From": "whatsapp:+919999999999", "WaId": "919999999999"})
    assert "Please provide your phone number" in res
    
    # Skip phone
    mock_chan_select.eq().eq().eq().execute.return_value = MagicMock(data=[{
        "id": "chan-1", "state": "awaiting_phone", "profile_completed": False,
        "customers": {"id": "cust-1", "name": "John Doe"}
    }])
    res = await twilio_whatsapp_service.process_update({"Body": "skip", "From": "whatsapp:+919999999999", "WaId": "919999999999"})
    assert "Profile saved. Now send your order." in res

@patch("app.services.twilio_whatsapp_service.supabase_client")
@patch("app.services.twilio_whatsapp_service.ActionCardController.create_card")
@patch("app.services.gemini.GeminiService.extract_order_details")
@pytest.mark.asyncio
async def test_twilio_order_extraction(mock_extract, mock_create, mock_supa):
    """Test text order is extracted and action card created"""
    from app.services.twilio_whatsapp_service import twilio_whatsapp_service
    
    mock_chan_select = MagicMock()
    mock_chan_select.eq().eq().eq().execute.return_value = MagicMock(data=[{
        "id": "chan-1", "state": "ready", "profile_completed": True, "channel_user_id": "12345",
        "customers": {"id": "cust-1", "name": "John Doe"}
    }])
    def mock_table(t):
        mock_t = MagicMock()
        mock_t.select.return_value = mock_chan_select
        return mock_t
    mock_supa.table.side_effect = mock_table
    
    mock_extract.return_value = {
        "customer_name": "John Doe",
        "items": [{"name": "Milk", "quantity": "1", "unit": "liter"}],
        "type": "ORDER"
    }
    
    res = await twilio_whatsapp_service.process_update({"Body": "send 1 liter milk", "From": "whatsapp:+919999999999", "WaId": "919999999999"})
    assert "Order received. Shopkeeper will review." in res
    
    mock_create.assert_called_once()
    args, kwargs = mock_create.call_args
    card_data = args[0]
    assert card_data["source"] == "whatsapp"
    assert card_data["metadata"]["whatsapp_wa_id"] == "12345"

@patch("app.services.twilio_whatsapp_service.supabase_client")
@pytest.mark.asyncio
async def test_twilio_random_text_rejection(mock_supa):
    from app.services.twilio_whatsapp_service import twilio_whatsapp_service
    mock_chan_select = MagicMock()
    mock_chan_select.eq().eq().eq().execute.return_value = MagicMock(data=[{
        "id": "chan-1", "state": "ready", "profile_completed": True,
        "customers": {"id": "cust-1", "name": "John Doe"}
    }])
    def mock_table(t):
        mock_t = MagicMock()
        mock_t.select.return_value = mock_chan_select
        return mock_t
    mock_supa.table.side_effect = mock_table
    
    res = await twilio_whatsapp_service.process_update({"Body": "how are you?", "From": "whatsapp:+919999999999", "WaId": "919999999999"})
    assert "Please send a grocery order" in res
