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
    settings.TELEGRAM_BOT_TOKEN = "fake_token_123"
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

    mock_send_message.assert_called_with("123", "Order received. Shopkeeper will review.\nYou can check recent orders with /orders.")

@pytest.mark.asyncio
async def test_telegram_voice_order(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    settings.TELEGRAM_BOT_TOKEN = "fake_token_123"
    
    # Mock requests for file path and download
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"ok": True, "result": {"file_path": "voice/file_12.ogg"}}
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.content = b"audio_data"
    mock_requests.get.side_effect = [mock_resp1, mock_resp2]
    
    mock_gemini.transcribe_audio_file.return_value = "5 kg sugar voice"
    mock_gemini.extract_order_details.return_value = {"items": []}
    
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "voice": {"file_id": "file123"}, "message_id": 999}})
    
    mock_gemini.transcribe_audio_file.assert_called_with(b"audio_data", "file_12.ogg", "audio/ogg")
    
    mock_action_card.create_card.assert_called_once()
    created_card = mock_action_card.create_card.call_args[0][0]
    assert created_card["metadata"]["input_type"] == "voice"
    assert created_card["metadata"]["pipeline"] == "gemini_gemini"
    assert created_card["metadata"]["telegram_message_id"] == 999
    assert created_card["transcript"] == "5 kg sugar voice"
    
    mock_send_message.assert_called_with("123", "Order received. Shopkeeper will review.\nYou can check recent orders with /orders.")

@pytest.mark.asyncio
async def test_telegram_voice_order_wav(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"ok": True, "result": {"file_path": "voice/file_12.wav"}}
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.content = b"audio_data"
    mock_requests.get.side_effect = [mock_resp1, mock_resp2]
    
    mock_gemini.transcribe_audio_file.return_value = "5 kg sugar voice"
    mock_gemini.extract_order_details.return_value = {"items": []}
    
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "audio": {"file_id": "file123"}}})
    
    mock_gemini.transcribe_audio_file.assert_called_with(b"audio_data", "file_12.wav", "audio/wav")

@pytest.mark.asyncio
async def test_telegram_voice_ffmpeg_fallback(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"ok": True, "result": {"file_path": "voice/file_12.ogg"}}
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.content = b"audio_data"
    mock_requests.get.side_effect = [mock_resp1, mock_resp2]
    
    # First call fails, second call (fallback) succeeds
    mock_gemini.transcribe_audio_file.side_effect = [Exception("Gemini rejected ogg"), "5 kg sugar fallback"]
    mock_gemini.extract_order_details.return_value = {"items": []}
    
    with patch("subprocess.run") as mock_subprocess:
        mock_subprocess.return_value = MagicMock()
        # Mock the wav_content since open() is used internally
        with patch("builtins.open", MagicMock()) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b"wav_data"
            await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "voice": {"file_id": "file123"}}})
            
    assert mock_gemini.transcribe_audio_file.call_count == 2
    mock_gemini.transcribe_audio_file.assert_any_call(b"audio_data", "file_12.ogg", "audio/ogg")
    mock_gemini.transcribe_audio_file.assert_any_call(b"wav_data", "fallback.wav", "audio/wav")

@pytest.mark.asyncio
async def test_telegram_catalog_pricing(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    
    mock_gemini.extract_order_details.return_value = {
        "items": [
            {"name": "sugar", "quantity": 5},
            {"name": "unknown_item", "quantity": 1}
        ]
    }
    
    with patch("app.services.matching_service.matching_service.match_product") as mock_match:
        # Match sugar, fail unknown_item
        def side_effect(name, shop_id):
            if name == "sugar":
                return {"canonical_name": "Sugar 1kg", "unit_price": 50.0, "resolution_status": "matched"}
            return {"resolution_status": "unmatched"}
        mock_match.side_effect = side_effect
        
        await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "5 kg sugar and 1 unknown item"}})
        
        created_card = mock_action_card.create_card.call_args[0][0]
        
        assert created_card["shop_id"] == "shop_123"
        assert created_card["metadata"]["telegram_user_id"] == "456"
        
        items = created_card["items"]
        assert len(items) == 2
        
        sugar_item = next(i for i in items if i["raw_name"] == "sugar")
        assert sugar_item["price"] == 50.0
        assert sugar_item["resolution_status"] == "matched"
        assert sugar_item["canonical_name"] == "Sugar 1kg"
        
        unknown_item = next(i for i in items if i["raw_name"] == "unknown_item")
        assert unknown_item["price"] is None
        assert unknown_item["resolution_status"] == "unmatched"

@pytest.mark.asyncio
async def test_telegram_orders_command(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    
    # Mock orders fetch
    mock_supabase.table().select().eq().order().limit().execute.return_value.data = [
        {
            "id": "card_12345",
            "status": "pending",
            "created_at": "2023-01-01T12:00:00Z",
            "items": [{"name": "Sugar"}]
        }
    ]
    
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "/orders"}})
    
    assert mock_send_message.call_args[0][1].startswith("Your recent orders:")
    assert "ID: card_123" in mock_send_message.call_args[0][1]
    assert "Status: Pending" in mock_send_message.call_args[0][1]
    assert "Sugar" in mock_send_message.call_args[0][1]

@pytest.mark.asyncio
async def test_telegram_voice_failure_network(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    mock_requests.get.side_effect = Exception("Network error fake_token_123")
    settings.TELEGRAM_BOT_TOKEN = "fake_token_123"
    
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "voice": {"file_id": "file123"}}})
    mock_send_message.assert_called_with("123", "Sorry, I could not download the voice message. Please try again or send text.")

@pytest.mark.asyncio
async def test_telegram_voice_getFile_ok_false(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": False, "error_code": 400, "description": "Bad Request"}
    mock_requests.get.return_value = mock_resp
    
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "voice": {"file_id": "file123"}}})
    mock_send_message.assert_called_with("123", "Sorry, I could not download the voice message. Please try again or send text.")

@pytest.mark.asyncio
async def test_telegram_voice_getFile_missing_path(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "result": {}}
    mock_requests.get.return_value = mock_resp
    
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "voice": {"file_id": "file123"}}})
    mock_send_message.assert_called_with("123", "Sorry, I could not download the voice message. Please try again or send text.")

@pytest.mark.asyncio
async def test_telegram_voice_download_non_200(mock_supabase, mock_gemini, mock_requests, mock_action_card, mock_send_message):
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "cust1", "name": "John Doe", "telegram_state": "ready", "profile_completed": True}]
    
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"ok": True, "result": {"file_path": "path.ogg"}}
    
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 500
    
    mock_requests.get.side_effect = [mock_resp1, mock_resp2]
    
    await telegram_service.process_update({"message": {"chat": {"id": 123}, "from": {"id": 456}, "voice": {"file_id": "file123"}}})
    mock_send_message.assert_called_with("123", "Sorry, I could not download the voice message. Please try again or send text.")
