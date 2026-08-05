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


def make_meta_msg(msg_id, text, profile_completed=False):
    return NormalizedInboundMessage(
        shop_id="shop1",
        customer_id="cust1",
        channel="meta_whatsapp",
        provider_message_id=msg_id,
        message_type="text",
        raw_text=text,
        metadata={"customer_profile_completed": profile_completed},
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


def test_meta_requires_name_address_and_specific_delivery_time():
    message = make_meta_msg("meta-1", "5 kilo aata bhej dena")
    missing = IntentRouter._missing_required_order_fields(
        {
            "customer_name": "WhatsApp Customer",
            "delivery_address": "",
            "delivery_time_normalized": None,
            "delivery_time_confidence": 0.2,
        },
        message,
    )

    assert missing == ["customer_name", "delivery_address", "delivery_time"]


def test_verified_meta_profile_can_supply_existing_name_and_address():
    message = make_meta_msg("meta-2", "kal 9:30 pm 5 kilo aata bhej dena", True)
    assert (
        IntentRouter._missing_required_order_fields(
            {
                "customer_name": "Danish",
                "delivery_address": "Batla House Jamia Nagar",
                "delivery_time_normalized": "2026-07-28 9:30 PM",
                "delivery_time_confidence": 0.9,
            },
            message,
        )
        == []
    )


def test_restaurant_dine_in_requires_table_not_delivery_details():
    message = make_meta_msg("meta-restaurant-1", "table 4 ke liye 2 thali")
    with patch(
        "app.services.intent_router.business_config_service.get_config",
        return_value=MagicMock(business_type=MagicMock(value="restaurant")),
    ):
        missing = IntentRouter._missing_required_order_fields(
            {
                "customer_name": "Danish",
                "takeaway_delivery_dine_in": "Dine-in",
                "table_number": "4",
            },
            message,
        )
    assert missing == []


def test_restaurant_delivery_requires_address_and_time():
    message = make_meta_msg("meta-restaurant-2", "2 thali delivery")
    with patch(
        "app.services.intent_router.business_config_service.get_config",
        return_value=MagicMock(business_type=MagicMock(value="restaurant")),
    ):
        missing = IntentRouter._missing_required_order_fields(
            {
                "customer_name": "Danish",
                "takeaway_delivery_dine_in": "delivery",
            },
            message,
        )
    assert missing == ["delivery_address", "delivery_time"]


def test_restaurant_unspecified_fulfillment_is_collected():
    message = make_meta_msg("meta-restaurant-3", "2 paneer tikka")
    with patch(
        "app.services.intent_router.business_config_service.get_config",
        return_value=MagicMock(business_type=MagicMock(value="restaurant")),
    ):
        missing = IntentRouter._missing_required_order_fields(
            {"customer_name": "Danish"},
            message,
        )
    assert missing == ["fulfillment_type"]


def test_meta_verified_name_beats_hallucinated_name_not_present_in_message():
    message = make_meta_msg(
        "meta-name-1",
        "kal 5 kilo aata bhej dena",
        profile_completed=True,
    )
    safe_item = MagicMock()
    safe_item.model_dump.return_value = {
        "name": "Aata",
        "quantity": 5,
        "unit": "kg",
        "price": 45,
    }

    with (
        patch.object(
            IntentRouter,
            "_get_customer",
            return_value={
                "id": "cust1",
                "name": "Danish",
                "phone": "+919012345678",
                "default_address": "Batla House Jamia Nagar",
            },
        ),
        patch(
            "app.routes.endpoints._safe_items_from_extracted",
            return_value=[safe_item],
        ),
        patch(
            "app.services.time_parser.parse_delivery_time",
            return_value={
                "normalized": "2026-07-28 5:30 PM",
                "confidence": 0.95,
                "warning": None,
            },
        ),
        patch(
            "app.services.confidence_scorer.ConfidenceScorer.calculate_confidence",
            return_value=(95, "high", []),
        ),
    ):
        card = IntentRouter._build_card_data(
            {
                "customer_name": "Rahul",
                "delivery_address": "Batla House Jamia Nagar",
                "delivery_time_raw": "kal 5:30 pm",
                "items": [{"name": "aata", "quantity": 5, "unit": "kg"}],
            },
            message,
            "inbound-name-1",
        )

    assert card["customer_name"] == "Danish"


def test_meta_explicit_order_name_can_override_saved_profile_for_that_order():
    message = make_meta_msg(
        "meta-name-2",
        "5 kilo aata bhej dena naam Rahul",
        profile_completed=True,
    )
    assert IntentRouter._has_explicit_customer_name(
        message.raw_text, "Rahul"
    )
    assert not IntentRouter._has_explicit_customer_name(
        "5 kilo aata bhej dena", "Rahul"
    )


def test_meta_collected_profile_fields_are_cleaned_deterministically():
    assert IntentRouter._clean_collected_name("mera naam Danish") == "Danish"
    assert (
        IntentRouter._clean_collected_address(
            "address: Batla House Jamia Nagar"
        )
        == "Batla House Jamia Nagar"
    )


@pytest.mark.asyncio
async def test_meta_follow_up_is_merged_into_pending_order_before_creation():
    conversation = {
        "id": "conv-meta",
        "shop_id": "shop1",
        "customer_id": "cust1",
        "channel": "meta_whatsapp",
        "state": "collecting_details",
        "draft_payload": {
            "original_text": (
                "5 kilo aata bhej dena. Naam Danish, "
                "address Batla House Jamia Nagar."
            ),
            "missing_fields": ["delivery_time"],
            "requires_confirmation": False,
        },
    }
    message = make_meta_msg("meta-follow-up", "kal 9:30 pm bhej dena")
    completed_card = {
        "items": [{"name": "Aata", "quantity": 5, "unit": "kg"}],
        "customer_name": "Danish",
        "delivery_address": "Batla House Jamia Nagar",
        "delivery_time_normalized": "2026-07-28 9:30 PM",
        "delivery_time_confidence": 0.9,
    }

    with (
        patch.object(
            GeminiService,
            "extract_order_details",
            new_callable=AsyncMock,
            return_value={"items": [{"name": "aata", "quantity": 5}]},
        ) as extract,
        patch.object(IntentRouter, "_build_card_data", return_value=completed_card),
        patch.object(IntentRouter, "_update_conversation", return_value=True),
        patch.object(
            IntentRouter, "_conditional_conversation_update", return_value=True
        ),
        patch.object(IntentRouter, "_update_inbound_status", return_value=True),
        patch.object(IntentRouter, "_persist_verified_meta_profile"),
        patch.object(IntentRouter, "_require_owner_id", return_value="owner1"),
        patch.object(
            IntentRouter, "_order_received_reply", return_value="Order received"
        ),
        patch(
            "app.services.intent_router.ActionCardController.create_card",
            return_value={"id": "card1"},
        ) as create_card,
    ):
        result = await IntentRouter._handle_collecting_details(
            conversation, message, "inbound-follow-up"
        )

    merged_text = extract.await_args.args[0]
    assert "5 kilo aata" in merged_text
    assert "Batla House Jamia Nagar" in merged_text
    assert "kal 9:30 pm" in merged_text
    create_card.assert_called_once_with(completed_card, user_id="owner1")
    assert result["status"] == "processed"


@pytest.mark.asyncio
async def test_meta_short_kl_time_reply_overrides_llm_that_drops_the_day():
    conversation = {
        "id": "conv-meta",
        "shop_id": "shop1",
        "customer_id": "cust1",
        "channel": "meta_whatsapp",
        "state": "collecting_details",
        "draft_payload": {
            "original_text": (
                "5 kilo aata bhej dena. Naam Danish, "
                "address Batla House Jamia Nagar."
            ),
            "missing_fields": ["delivery_time"],
            "requires_confirmation": False,
        },
    }
    message = make_meta_msg("meta-short-time", "kl 5:30 pm")
    captured = {}

    def build_card(extracted, _message, _inbound_id, _business_context=None):
        captured.update(extracted)
        return {
            "items": [{"name": "Aata", "quantity": 5, "unit": "kg"}],
            "customer_name": "Danish",
            "delivery_address": "Batla House Jamia Nagar",
            "delivery_time_normalized": extracted.get(
                "delivery_time_normalized"
            ),
            "delivery_time_confidence": extracted.get(
                "delivery_time_confidence"
            ),
        }

    with (
        patch.object(
            GeminiService,
            "extract_order_details",
            new_callable=AsyncMock,
            return_value={
                "items": [{"name": "aata", "quantity": 5}],
                "delivery_time_raw": "5:30 pm",
            },
        ),
        patch.object(IntentRouter, "_build_card_data", side_effect=build_card),
        patch.object(IntentRouter, "_update_conversation", return_value=True),
        patch.object(
            IntentRouter, "_conditional_conversation_update", return_value=True
        ),
        patch.object(IntentRouter, "_update_inbound_status", return_value=True),
        patch.object(IntentRouter, "_persist_verified_meta_profile"),
        patch.object(IntentRouter, "_require_owner_id", return_value="owner1"),
        patch.object(
            IntentRouter, "_order_received_reply", return_value="Order received"
        ),
        patch(
            "app.services.intent_router.ActionCardController.create_card",
            return_value={"id": "card1"},
        ),
    ):
        result = await IntentRouter._handle_collecting_details(
            conversation, message, "inbound-short-time"
        )

    assert result["status"] == "processed"
    assert captured["delivery_time_raw"] == "kl 5:30 pm"
    assert captured["delivery_time_normalized"].endswith("5:30 PM")
    assert captured["delivery_time_confidence"] >= 0.8


@pytest.mark.asyncio
async def test_meta_follow_up_does_not_duplicate_an_already_claimed_draft():
    conversation = {
        "id": "conv-meta",
        "shop_id": "shop1",
        "customer_id": "cust1",
        "channel": "meta_whatsapp",
        "state": "collecting_details",
        "draft_payload": {
            "original_text": "5 kilo aata bhej dena",
            "missing_fields": ["delivery_time"],
            "requires_confirmation": False,
        },
    }
    message = make_meta_msg("meta-race", "kal 9:30 pm bhej dena")

    with (
        patch.object(
            IntentRouter, "_conditional_conversation_update", return_value=False
        ),
        patch.object(IntentRouter, "_update_inbound_status", return_value=True),
        patch.object(
            GeminiService, "extract_order_details", new_callable=AsyncMock
        ) as extract,
        patch(
            "app.services.intent_router.ActionCardController.create_card"
        ) as create_card,
    ):
        result = await IntentRouter._handle_collecting_details(
            conversation, message, "inbound-race"
        )

    extract.assert_not_awaited()
    create_card.assert_not_called()
    assert result["status"] == "skipped"

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
        ("kl 9:30 pm me 5 kilo aata dena", "new_order", 0.95),
        ("5 kilo aata", "new_order", 0.95),
        (
            "50 kilo aata aur 100 kilo chini or 1 litre oil bhej dena "
            "naam Danish address Batla House Jamia Nagar kal 9:30 pm me bhej dena",
            "new_order",
            0.95,
        ),
        ("दस किलो आटा भेज देना", "new_order", 0.95),
        ("Where is my order?", "order_tracking", 0.95),
        ("trackmyorder", "order_tracking", 0.95),
        ("mera order kaha hai", "order_tracking", 0.95),
        ("मेरा ऑर्डर कहाँ है", "order_tracking", 0.95),
        ("I need help", "business_support", 0.90),
        (
            "order jo kiya h tha uska bill bhej dijiye na",
            "payment_query",
            0.90,
        ),
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
    "text",
    [
        "2 plate chicken biryani medium spicy aur 1 paneer tikka less spicy",
        "Do plate chicken biryani medium spicy parcel",
        "1 paneer tikka less spicy",
    ],
)
def test_restaurant_catalog_orders_are_classified_without_ai(text):
    classification = IntentRouter.classify_intent_deterministically(
        text,
        business_context={
            "business_type": "restaurant",
            "offerings": ["Chicken Biryani", "Paneer Tikka"],
        },
    )

    assert classification is not None
    assert classification.intent.value == "new_order"
    assert classification.confidence >= 0.95


def test_restaurant_units_do_not_change_grocery_classification_rules():
    assert IntentRouter.classify_intent_deterministically("2 plate biryani") is None


@pytest.mark.parametrize(
    ("text", "expected_items"),
    [
        ("Send 10 kg rice tomorrow", [("rice", 10, "kg")]),
        ("kl 9:30 pm me 5 kilo aata dena", [("aata", 5, "kilo")]),
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


def test_customer_can_fetch_latest_bill_for_own_shop_and_identity(mock_supabase):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = MagicMock(
        data=[
            {
                "id": "order-1",
                "shop_id": "shop1",
                "total_amount": 675.0,
                "lifecycle_status": "out_for_delivery",
            }
        ]
    )
    mock_supabase.table.return_value = query

    with patch(
        "app.services.bill_link_service.ensure_public_bill_link",
        return_value="https://phone-erp.vercel.app/bill/secure-token",
    ) as mock_link, patch.object(IntentRouter, "_update_conversation"), patch.object(
        IntentRouter, "_update_inbound_status"
    ):
        result = IntentRouter._handle_bill_request(
            make_msg("bill-1", "mera bill bhej do"),
            {"id": "conv1"},
            "inbound-1",
        )

    query.eq.assert_any_call("shop_id", "shop1")
    query.eq.assert_any_call("customer_id", "cust1")
    mock_link.assert_called_once_with(
        "order-1",
        "shop1",
        db_client=mock_supabase,
    )
    assert result["status"] == "processed"
    assert "₹675.00" in result["reply_message"]
    assert "secure-token" in result["reply_message"]


def test_customer_bill_request_handles_no_orders(mock_supabase):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value = query

    with patch.object(IntentRouter, "_update_inbound_status"):
        result = IntentRouter._handle_bill_request(
            make_msg("bill-2", "bill bhejo"),
            {"id": "conv1"},
            "inbound-2",
        )

    assert result["status"] == "processed"
    assert "koi order nahi mila" in result["reply_message"]


def test_tracking_reads_latest_order_from_customer_shop_scope(mock_supabase):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = MagicMock(data=[{
        "id": "order-1",
        "order_number": 101,
        "lifecycle_status": "out_for_delivery",
        "total_amount": 675,
        "created_at": "2026-07-16T10:00:00+00:00",
    }])
    mock_supabase.table.return_value = query

    with patch.object(
        IntentRouter,
        "_create_portal_link",
        return_value="https://phone-erp.vercel.app/customer/access?token=private",
    ), patch.object(IntentRouter, "_update_conversation"), patch.object(
        IntentRouter, "_update_inbound_status"
    ):
        result = IntentRouter._handle_tracking_request(
            make_msg("tracking-1", "mera order kaha hai"),
            {"id": "conv-1"},
            "inbound-1",
        )

    query.eq.assert_any_call("shop_id", "shop1")
    query.eq.assert_any_call("customer_id", "cust1")
    assert "Out For Delivery" in result["reply_message"]
    assert "customer/access?token=private" in result["reply_message"]


def test_tracking_returns_portal_link_before_owner_approval(mock_supabase):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.side_effect = [
        MagicMock(data=[]),
        MagicMock(data=[{"id": "ac-1", "status": "pending"}]),
    ]
    mock_supabase.table.return_value = query

    with patch.object(
        IntentRouter,
        "_create_portal_link",
        return_value="https://phone-erp.vercel.app/customer/access#token=stable",
    ), patch.object(IntentRouter, "_update_conversation"), patch.object(
        IntentRouter, "_update_inbound_status"
    ):
        result = IntentRouter._handle_tracking_request(
            make_msg("tracking-pending", "trackmyorder"),
            {"id": "conv-1"},
            "inbound-1",
        )

    assert result["status"] == "processed"
    assert "review" in result["reply_message"].lower()
    assert "customer/access#token=stable" in result["reply_message"]


def test_tracking_returns_portal_link_when_status_lookup_fails(mock_supabase):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.side_effect = RuntimeError("status store unavailable")
    mock_supabase.table.return_value = query

    with patch.object(
        IntentRouter,
        "_create_portal_link",
        return_value="https://phone-erp.vercel.app/customer/access#token=stable",
    ), patch.object(IntentRouter, "_update_conversation"), patch.object(
        IntentRouter, "_update_inbound_status"
    ):
        result = IntentRouter._handle_tracking_request(
            make_msg("tracking-fallback", "trackmyorder"),
            {"id": "conv-1"},
            "inbound-1",
        )

    assert result["status"] == "processed"
    assert "customer/access#token=stable" in result["reply_message"]


def test_order_received_reply_survives_portal_link_failure():
    with patch.object(IntentRouter, "_create_portal_link", return_value=None):
        reply = IntentRouter._order_received_reply("shop1", "cust1", "whatsapp")
    assert reply == "Order received. Shopkeeper will review it."


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

    def build_card(_extracted, msg, _inbound_id, _business_context=None):
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
