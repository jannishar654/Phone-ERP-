import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.intent_router import IntentRouter
from app.schemas.inbound import NormalizedInboundMessage
import datetime

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
         patch.object(IntentRouter, '_update_inbound_status'), \
         patch.object(IntentRouter, '_get_or_create_conversation') as mock_conv:
        yield mock_conv

def make_msg(msg_id, text):
    return NormalizedInboundMessage(
        shop_id="shop1",
        customer_id="cust1",
        channel="whatsapp",
        provider_message_id=msg_id,
        message_type="text",
        raw_text=text,
        metadata={}
    )

@pytest.mark.asyncio
async def test_concurrent_confirmation(mock_supabase, mock_gemini, mock_action_card, mock_helpers):
    """
    Test that if two requests confirm the same conversation simultaneously,
    only one succeeds in transitioning the state and creating an action card.
    """
    future_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()
    mock_helpers.return_value = {
        "id": "conv1", "shop_id": "shop1", "customer_id": "cust1", "channel": "whatsapp",
        "state": "awaiting_confirmation", "expires_at": future_time,
        "draft_payload": {"items": [{"name": "bread"}]}
    }

    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])

    # We need to simulate atomic state updates.
    # IntentRouter calls _update_conversation(conv_id, {"state": "creating_order"}, "awaiting_confirmation")
    # If successful, the mock should return [{"id": "conv1"}] for the first call, and [] for the second call.
    update_mock = MagicMock()

    # We use a stateful mock for the execute call to simulate race conditions
    call_count = 0
    def side_effect_execute():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MagicMock(data=[{"id": "conv1"}])
        else:
            return MagicMock(data=[])

    mock_supabase.table().update().eq().eq().execute.side_effect = side_effect_execute

    # We run two process_inbound_message concurrently
    msg1 = make_msg("msgC1", "yes")
    msg2 = make_msg("msgC2", "yes")

    results = await asyncio.gather(
        IntentRouter.process_inbound_message(msg1),
        IntentRouter.process_inbound_message(msg2)
    )

    # Only one should have successfully processed the confirmation
    success_count = sum(1 for r in results if r["status"] == "processed" and "confirmed" in r["reply_message"].lower())
    assert success_count == 1

    # Action card should only be created once
    assert mock_action_card.create_card.call_count == 1


@pytest.mark.asyncio
async def test_confirmation_failure_releases_creating_order_state(
    mock_supabase, mock_gemini, mock_action_card, mock_helpers
):
    future_time = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
    ).isoformat()
    mock_helpers.return_value = {
        "id": "conv1",
        "shop_id": "shop1",
        "customer_id": "cust1",
        "channel": "whatsapp",
        "state": "awaiting_confirmation",
        "expires_at": future_time,
        "draft_payload": {"items": [{"name": "bread", "quantity": 1}]},
    }
    mock_supabase.table().select().eq().eq().execute.return_value = MagicMock(data=[])
    mock_supabase.table().update().eq().eq().execute.return_value = MagicMock(
        data=[{"id": "conv1"}]
    )

    with patch.object(IntentRouter, "_get_owner_id", return_value=None):
        result = await IntentRouter.process_inbound_message(
            make_msg("msg-owner-missing", "yes")
        )

    assert result["status"] == "error"
    mock_action_card.create_card.assert_not_called()
    update_payloads = [
        call.args[0]
        for call in mock_supabase.table().update.call_args_list
        if call.args
    ]
    assert {"state": "awaiting_confirmation"} in update_payloads
