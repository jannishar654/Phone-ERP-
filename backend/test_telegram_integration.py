import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.telegram_service import telegram_service, normalize_phone
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
        mock.transcribe_audio_file = AsyncMock()
        yield mock

@pytest.fixture
def mock_requests():
    with patch("app.services.telegram_service.requests") as mock:
        yield mock

@pytest.fixture
def mock_action_card():
    with patch("app.services.telegram_service.ActionCardController") as mock:
        yield mock

@pytest.fixture
def mock_send_message():
    with patch.object(telegram_service, "send_message") as mock:
        yield mock

def test_normalize_phone():
    assert normalize_phone("skip") is None
    assert normalize_phone("SKIP") is None
    assert normalize_phone("9999999999") == "+919999999999"
    assert normalize_phone("+919999999999") == "+919999999999"
    assert normalize_phone("919999999999") == "+919999999999"
    assert normalize_phone("99 99 999 999") == "+919999999999"
    assert normalize_phone("123") is None

def test_webhook_secret_validation():
    settings.TELEGRAM_WEBHOOK_SECRET = "super_secret"
    response = client.post("/telegram/webhook", json={"message": {"text": "/start"}})
    assert response.status_code == 401
    response = client.post("/telegram/webhook", json={"message": {"text": "/start"}}, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
    assert response.status_code == 401
    response = client.post("/telegram/webhook", json={"message": {"text": "/start"}}, headers={"X-Telegram-Bot-Api-Secret-Token": "super_secret"})
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_telegram_start_new_customer(mock_supabase, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = []
    mock_supabase.table().insert().execute.return_value.data = [{"id": "cust1", "telegram_state": "awaiting_name", "profile_completed": False}]
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "/start"}})
    mock_send_message.assert_called_with("123", "Welcome to PhoneERP. Please tell me your name.")

@pytest.mark.asyncio
async def test_telegram_awaiting_name(mock_supabase, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "telegram_state": "awaiting_name", "profile_completed": False}]
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "John Doe"}})
    mock_send_message.assert_called_with("123", "Thanks! What is your delivery address?")

@pytest.mark.asyncio
async def test_telegram_awaiting_address(mock_supabase, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "telegram_state": "awaiting_address", "profile_completed": False}]
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "123 Main St"}})
    mock_send_message.assert_called_with("123", "Please provide your phone number (or type 'skip').")

@pytest.mark.asyncio
async def test_telegram_awaiting_phone_skip(mock_supabase, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "telegram_state": "awaiting_phone", "profile_completed": False}]
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "skip"}})
    mock_send_message.assert_called_with("123", "Profile saved. Now send your order.")

@pytest.mark.asyncio
async def test_telegram_awaiting_phone_valid(mock_supabase, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "telegram_state": "awaiting_phone", "profile_completed": False}]
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "9999999999"}})
    mock_send_message.assert_called_with("123", "Profile saved. Now send your order.")

@pytest.mark.asyncio
async def test_telegram_ready_order_text(mock_supabase, mock_gemini, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "default_address": "123 Main St", "phone": "+919999999999", "telegram_state": "ready", "profile_completed": True}]
    mock_gemini.extract_order_details.return_value = {"customer_name": None, "delivery_address": None, "phone": None, "items": [], "operations": []}
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "5 kg sugar"}})
    mock_action_card.create_card.assert_called_once()
    created_card = mock_action_card.create_card.call_args[0][0]
    assert created_card["customer_name"] == "John Doe"
    assert created_card["delivery_address"] == "123 Main St"
    assert created_card["phone"] == "+919999999999"
    assert created_card["metadata"]["input_type"] == "text"
    assert created_card["metadata"]["pipeline"] == "gemini_gemini"

@pytest.mark.asyncio
async def test_telegram_voice_order(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    
    # Mock requests for file path and download
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {"result": {"file_path": "voice/file_12.ogg"}}
    mock_resp2 = MagicMock()
    mock_resp2.content = b"audio_data"
    mock_requests.get.side_effect = [mock_resp1, mock_resp2]
    
    mock_gemini.transcribe_audio_file.return_value = "5 kg sugar voice"
    mock_gemini.extract_order_details.return_value = {"items": []}
    
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "voice": {"file_id": "file123"}, "message_id": 999}})
    
    mock_action_card.create_card.assert_called_once()
    created_card = mock_action_card.create_card.call_args[0][0]
    assert created_card["metadata"]["input_type"] == "voice"
    assert created_card["metadata"]["pipeline"] == "gemini_gemini"
    assert created_card["metadata"]["telegram_message_id"] == 999
    assert created_card["transcript"] == "5 kg sugar voice"
    
    mock_send_message.assert_called_with("123", "Voice order received. Shopkeeper will review.")

@pytest.mark.asyncio
async def test_telegram_voice_failure(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    mock_requests.get.side_effect = Exception("Network error")
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "voice": {"file_id": "file123"}}})
    mock_send_message.assert_called_with("123", "Sorry, I could not download the voice message. Please try again or send text.")
