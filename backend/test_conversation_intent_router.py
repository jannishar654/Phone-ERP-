import pytest
import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from pydantic import ValidationError
from app.services.intent_router import IntentRouter
from app.services.gemini import GeminiService
from app.schemas.inbound import NormalizedInboundMessage

@pytest.fixture
def mock_supabase():
    with patch("app.services.intent_router.supabase_client") as mock:
        yield mock

@pytest.fixture
def mock_gemini():
    with patch("app.services.intent_router.GeminiService") as mock:
        yield mock

@pytest.fixture
def mock_action_card():
    with patch("app.services.intent_router.ActionCardController") as mock:
        yield mock

@pytest.fixture
def mock_helpers():
    with patch.object(IntentRouter, '_get_owner_id', return_value="owner1"), \
         patch.object(IntentRouter, '_get_customer', return_value={"name": "Test", "phone": "1234567890", "id": "cust1"}), \
         patch.object(IntentRouter, '_update_conversation'), \
         patch.object(IntentRouter, '_update_inbound_status'), \
         patch.object(IntentRouter, '_get_or_create_conversation') as mock_conv:
        yield mock_conv

def make_msg(msg_id, text, shop_id="shop1", cust_id="cust1"):
    return NormalizedInboundMessage(
        shop_id=shop_id,
        customer_id=cust_id,
        channel="whatsapp",
        provider_message_id=msg_id,
        message_type="text",
        raw_text=text,
        metadata={}
    )


def test_normalized_message_rejects_missing_provider_id():
    with pytest.raises(ValidationError):
        make_msg("", "send 1 kg rice")


def test_normalized_message_rejects_unknown_channel():
    with pytest.raises(ValidationError):
        NormalizedInboundMessage(
            shop_id="shop1",
            customer_id="cust1",
            channel="email",
            provider_message_id="msg-1",
            message_type="text",
            raw_text="send 1 kg rice",
        )


def test_normalized_message_rejects_oversized_metadata():
    with pytest.raises(ValidationError):
        NormalizedInboundMessage(
            shop_id="shop1",
            customer_id="cust1",
            channel="whatsapp",
            provider_message_id="msg-1",
            message_type="text",
            raw_text="send 1 kg rice",
            metadata={"payload": "x" * 17_000},
        )

@pytest.mark.asyncio
async def test_idempotency_duplicate_webhook(mock_supabase, mock_gemini, mock_action_card, mock_helpers):
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[{"id": "test"}])
    result = await IntentRouter.process_inbound_message(make_msg("msg123", "hello"))
    assert result["status"] == "skipped"
    mock_gemini.classify_intent.assert_not_called()

@pytest.mark.asyncio
async def test_expired_confirmation(mock_supabase, mock_gemini, mock_action_card, mock_helpers):
    past_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).isoformat()
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_helpers.return_value = {"id": "conv1", "shop_id": "shop1", "customer_id": "cust1", "channel": "whatsapp", "state": "awaiting_confirmation", "expires_at": past_time, "draft_payload": {"some": "data"}}

    mock_gemini.classify_intent = AsyncMock(return_value={"intent": "new_order", "confidence": 0.90})
    mock_gemini.extract_order_details = AsyncMock(return_value={"items": [{"name": "milk"}]})

    # Should early-return 'Draft expired' before calling order creation
    result = await IntentRouter.process_inbound_message(make_msg("msg1", "yes"))
    assert result["status"] == "processed"
    assert "expired" in result["reply_message"].lower()
    mock_action_card.create_card.assert_not_called()

@pytest.mark.asyncio
async def test_expired_confirmation_general_message(mock_supabase, mock_gemini, mock_action_card, mock_helpers):
    past_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).isoformat()
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_helpers.return_value = {"id": "conv1", "shop_id": "shop1", "customer_id": "cust1", "channel": "whatsapp", "state": "awaiting_confirmation", "expires_at": past_time, "draft_payload": {"some": "data"}}

    mock_gemini.classify_intent = AsyncMock(return_value={"intent": "general_message", "confidence": 0.99})

    result = await IntentRouter.process_inbound_message(make_msg("msg1", "yes"))
    assert result["status"] == "processed"
    assert "expired" in result["reply_message"].lower()
    mock_action_card.create_card.assert_not_called()

@pytest.mark.asyncio
async def test_model_timeout_invalid_json(mock_supabase, mock_gemini, mock_action_card, mock_helpers):
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_helpers.return_value = {"id": "conv1", "state": "idle"}
    mock_gemini.classify_intent = AsyncMock(side_effect=Exception("API Timeout"))

    result = await IntentRouter.process_inbound_message(make_msg("msg2", "maybe later"))
    assert result["status"] == "needs_review"
    assert "contact the business" in result["reply_message"].lower()
    mock_action_card.create_card.assert_not_called()


@pytest.mark.parametrize(
    ("text", "expected_intent", "minimum_confidence"),
    [
        ("What is the price of rice?", "price_enquiry", 0.95),
        ("Send 10 kg rice tomorrow", "new_order", 0.95),
        (
            "50 kilo aata aur 100 kilo chini or 1 litre oil bhej dena "
            "naam Danish address Batla House Jamia Nagar kal 9:30 pm me bhej dena",
            "new_order",
            0.95,
        ),
        ("दस किलो आटा भेज देना", "new_order", 0.95),
        ("Where is my order?", "order_tracking", 0.95),
        ("I need help", "business_support", 0.90),
    ],
)
def test_multilingual_deterministic_intent_fallback(
    text, expected_intent, minimum_confidence
):
    classification = IntentRouter.classify_intent_deterministically(text)

    assert classification is not None
    assert classification.intent.value == expected_intent
    assert classification.confidence >= minimum_confidence


@pytest.mark.parametrize(
    ("text", "expected_items"),
    [
        ("Send 10 kg rice tomorrow", [("rice", 10, "kg")]),
        (
            "50 kilo aata aur 100 kilo chini or 1 litre oil bhej dena "
            "naam Danish address Batla House Jamia Nagar kal 9:30 pm me bhej dena",
            [("aata", 50, "kilo"), ("chini", 100, "kilo"), ("oil", 1, "litre")],
        ),
        ("दस किलो आटा भेज देना", [("आटा", 10, "किलो")]),
    ],
)
def test_multilingual_order_extraction_fallback(text, expected_items):
    parsed = GeminiService._parse_order_fallback(text)
    actual_items = [
        (item["name"], item["quantity"], item["unit"]) for item in parsed["items"]
    ]

    assert actual_items == expected_items


@pytest.mark.asyncio
@patch("app.services.gemini.settings.GEMINI_API_KEY", "test-api-key")
@patch("app.services.gemini.genai.Client")
async def test_order_extraction_survives_gemini_outage(mock_client):
    mock_client.return_value.models.generate_content.side_effect = OSError(
        "provider unavailable"
    )

    parsed = await GeminiService.extract_order_details(
        "50 kilo aata aur 100 kilo chini or 1 litre oil bhej dena "
        "naam Danish address Batla House Jamia Nagar kal 9:30 pm me bhej dena"
    )

    assert parsed["customer_name"] == "Danish"
    assert parsed["delivery_address"] == "Batla House Jamia Nagar"
    assert [item["name"] for item in parsed["items"]] == ["aata", "chini", "oil"]


@pytest.mark.asyncio
async def test_general_message_never_creates_action_card(
    mock_supabase, mock_gemini, mock_action_card, mock_helpers
):
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_helpers.return_value = {"id": "conv1", "state": "idle"}
    mock_gemini.classify_intent = AsyncMock(
        return_value={"intent": "general_message", "confidence": 0.99}
    )

    result = await IntentRouter.process_inbound_message(make_msg("msg-general", "hello"))

    assert result["status"] == "processed"
    mock_action_card.create_card.assert_not_called()


@pytest.mark.asyncio
async def test_low_confidence_order_never_creates_action_card(
    mock_supabase, mock_gemini, mock_action_card, mock_helpers
):
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_helpers.return_value = {"id": "conv1", "state": "idle"}
    mock_gemini.classify_intent = AsyncMock(
        return_value={"intent": "new_order", "confidence": 0.45}
    )

    result = await IntentRouter.process_inbound_message(
        make_msg("msg-low", "maybe rice sometime")
    )

    assert result["status"] == "needs_review"
    mock_gemini.extract_order_details.assert_not_called()
    mock_action_card.create_card.assert_not_called()

@pytest.mark.asyncio
async def test_multilingual_yes_no_confirmation(mock_supabase, mock_gemini, mock_action_card, mock_helpers):
    future_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_helpers.return_value = {"id": "conv1", "shop_id": "shop1", "customer_id": "cust1", "channel": "whatsapp", "state": "awaiting_confirmation", "expires_at": future_time, "draft_payload": {"items": []}}
    mock_supabase.table().update().eq().eq().execute.return_value = MagicMock(data=[{"id": "conv1"}])

    result = await IntentRouter.process_inbound_message(make_msg("msg3", "haan"))
    assert result["status"] == "processed"
    assert "confirmed" in result["reply_message"]
    mock_action_card.create_card.assert_called_once()

    mock_action_card.reset_mock()
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_supabase.table().update().eq().eq().execute.return_value = MagicMock(data=[{"id": "conv1"}])

    result = await IntentRouter.process_inbound_message(make_msg("msg4", "nahi bhai"))
    assert result["status"] == "processed"
    assert "cancelled" in result["reply_message"]
    mock_action_card.create_card.assert_not_called()

@pytest.mark.asyncio
async def test_confirmation_exactly_one_action_card(mock_supabase, mock_gemini, mock_action_card, mock_helpers):
    future_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_supabase.table().update().eq().eq().execute.return_value = MagicMock(data=[{"id": "conv1"}])
    mock_helpers.return_value = {"id": "conv1", "shop_id": "shop1", "customer_id": "cust1", "channel": "whatsapp", "state": "awaiting_confirmation", "expires_at": future_time, "draft_payload": {"items": [{"name": "bread"}]}}

    await IntentRouter.process_inbound_message(make_msg("msg5", "yes"))
    assert mock_action_card.create_card.call_count == 1

@pytest.mark.asyncio
async def test_cross_shop_isolation(mock_supabase, mock_gemini, mock_action_card, mock_helpers):
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_helpers.side_effect = [
        {"id": "conv1", "shop_id": "shop1", "state": "idle"},
        {"id": "conv2", "shop_id": "shop2", "state": "idle"}
    ]
    mock_gemini.classify_intent = AsyncMock(return_value={"intent": "new_order", "confidence": 0.95})
    mock_gemini.extract_order_details = AsyncMock(
        return_value={"items": [{"name": "rice", "quantity": 1, "unit": "kg"}]}
    )

    def build_card(_extracted, msg, _inbound_id):
        return {
            "shop_id": msg.shop_id,
            "customer_id": msg.customer_id,
            "items": [{"name": "rice", "quantity": 1, "unit": "kg"}],
        }

    with patch.object(IntentRouter, "_build_card_data", side_effect=build_card):
        await IntentRouter.process_inbound_message(
            make_msg("msgA", "send 1 kg rice", shop_id="shop1", cust_id="custA")
        )
        mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
        await IntentRouter.process_inbound_message(
            make_msg("msgB", "send 1 kg rice", shop_id="shop2", cust_id="custB")
        )

    assert mock_action_card.create_card.call_count == 2
    first_card = mock_action_card.create_card.call_args_list[0].args[0]
    second_card = mock_action_card.create_card.call_args_list[1].args[0]
    assert (first_card["shop_id"], first_card["customer_id"]) == ("shop1", "custA")
    assert (second_card["shop_id"], second_card["customer_id"]) == ("shop2", "custB")
