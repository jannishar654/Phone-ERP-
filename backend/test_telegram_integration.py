import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.telegram_service import telegram_service
from app.config.settings import settings
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_settings():
    settings.TELEGRAM_DEFAULT_SHOP_ID = "shop_123"
    settings.TELEGRAM_DEFAULT_OWNER_ID = "owner_123"
    yield

@pytest.fixture
def mock_supabase():
    with patch("app.services.telegram_service.supabase_client") as mock:
        yield mock

@pytest.fixture
def mock_gemini():
    with patch("app.services.gemini.GeminiService") as mock:
        mock.extract_order_details = AsyncMock()
        yield mock

@pytest.fixture
def mock_action_card():
    with patch("app.services.telegram_service.ActionCardController") as mock:
        yield mock

@pytest.fixture
def mock_send_message():
    with patch.object(telegram_service, "send_message") as mock:
        yield mock

def test_webhook_secret_validation():
    # If secret is set, it must match
    settings.TELEGRAM_WEBHOOK_SECRET = "super_secret"
    
    # Missing header
    response = client.post("/telegram/webhook", json={"message": {"text": "/start"}})
    assert response.status_code == 401
    
    # Wrong header
    response = client.post("/telegram/webhook", json={"message": {"text": "/start"}}, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
    assert response.status_code == 401
    
    # Correct header
    response = client.post("/telegram/webhook", json={"message": {"text": "/start"}}, headers={"X-Telegram-Bot-Api-Secret-Token": "super_secret"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_telegram_start_new_customer(mock_supabase, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = []
    mock_supabase.table().insert().execute.return_value.data = [{
        "id": "cust1",
        "telegram_state": "awaiting_name",
        "profile_completed": False
    }]
    
    await telegram_service.process_update({
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456},
            "text": "/start"
        }
    })
    
    mock_send_message.assert_called_with("123", "Welcome to PhoneERP. Please tell me your name.")

@pytest.mark.asyncio
async def test_telegram_awaiting_name(mock_supabase, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{
        "id": "cust1",
        "telegram_state": "awaiting_name",
        "profile_completed": False
    }]
    
    await telegram_service.process_update({
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456},
            "text": "John Doe"
        }
    })
    
    mock_supabase.table().update.assert_called()
    mock_send_message.assert_called_with("123", "Thanks! What is your delivery address?")

@pytest.mark.asyncio
async def test_telegram_ready_order(mock_supabase, mock_gemini, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{
        "id": "cust1",
        "name": "John Doe",
        "default_address": "123 Main St",
        "telegram_state": "ready",
        "profile_completed": True
    }]
    
    mock_gemini.extract_order_details.return_value = {
        "customer_name": None,
        "delivery_address": None,
        "items": [],
        "operations": []
    }
    
    await telegram_service.process_update({
        "message": {
            "chat": {"id": 123},
            "from": {"id": 456},
            "text": "5 kg sugar"
        }
    })
    
    # Assert fallback was used
    mock_action_card.create_card.assert_called_once()
    created_card = mock_action_card.create_card.call_args[0][0]
    
    assert created_card["customer_name"] == "John Doe"
    assert created_card["delivery_address"] == "123 Main St"
    assert created_card["source"] == "telegram"
    assert created_card["metadata"]["telegram_user_id"] == "456"
    assert created_card["transcript"] == "5 kg sugar"
    
    mock_send_message.assert_called_with("123", "Order received. Shopkeeper will review.")
