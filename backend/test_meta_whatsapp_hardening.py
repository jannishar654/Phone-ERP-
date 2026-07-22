import os
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config.settings import settings
from app.services.meta_whatsapp_event_service import meta_whatsapp_event_service
from app.services.meta_whatsapp_service import meta_whatsapp_service
from app.services.delivery_notification_service import _meta_freeform_window_is_open


def _message_payload():
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "phone-1"},
                            "contacts": [
                                {
                                    "wa_id": "919012345678",
                                    "profile": {"name": "Danish"},
                                }
                            ],
                            "messages": [
                                {
                                    "id": "wamid-1",
                                    "from": "919012345678",
                                    "type": "text",
                                    "text": {"body": "5 kilo aata bhej dena"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _database_for_event_insert():
    database = MagicMock()
    event_table = MagicMock()
    event_table.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "event-1"}]
    )
    connection_table = MagicMock()
    connection_table.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "connection-1"}]
    )

    def table(name):
        if name == "whatsapp_webhook_events":
            return event_table
        if name == "whatsapp_connections":
            return connection_table
        raise AssertionError(f"Unexpected table {name}")

    database.table.side_effect = table
    return database, event_table


def test_verified_message_is_persisted_before_processing():
    database, event_table = _database_for_event_insert()
    connection = {
        "id": "connection-1",
        "shop_id": "shop-1",
        "waba_id": "waba-1",
        "phone_number_id": "phone-1",
        "status": "active",
    }
    with (
        patch(
            "app.services.meta_whatsapp_event_service.supabase_client", database
        ),
        patch.object(
            meta_whatsapp_service, "resolve_connection", return_value=connection
        ) as resolve_connection,
    ):
        event_ids = meta_whatsapp_event_service.persist_webhook_payload(
            _message_payload()
        )

    assert event_ids == ["event-1"]
    resolve_connection.assert_called_once_with(
        "phone-1", allow_default=False, raise_on_error=True
    )
    inserted = event_table.insert.call_args.args[0]
    assert inserted["provider_event_id"] == "wamid-1"
    assert inserted["shop_id"] == "shop-1"
    assert inserted["processing_status"] == "pending"
    assert inserted["payload"]["message"]["type"] == "text"


def test_unmapped_message_is_retained_as_unroutable():
    database, event_table = _database_for_event_insert()
    with (
        patch(
            "app.services.meta_whatsapp_event_service.supabase_client", database
        ),
        patch.object(meta_whatsapp_service, "resolve_connection", return_value=None),
    ):
        event_ids = meta_whatsapp_event_service.persist_webhook_payload(
            _message_payload()
        )

    assert event_ids == ["event-1"]
    inserted = event_table.insert.call_args.args[0]
    assert inserted["shop_id"] is None
    assert inserted["processing_status"] == "unroutable"
    assert inserted["last_error"] == "ConnectionNotMapped"


def test_token_reference_reads_only_allowlisted_server_environment_variable():
    connection = {"token_reference": "env:META_WHATSAPP_TOKEN_SHOP_A"}
    with patch.dict(os.environ, {"META_WHATSAPP_TOKEN_SHOP_A": "secret-token"}):
        assert meta_whatsapp_service._resolve_access_token(connection) == "secret-token"

    assert (
        meta_whatsapp_service._resolve_access_token(
            {"token_reference": "env:UNSAFE_ARBITRARY_SECRET"}
        )
        is None
    )


def test_default_shop_fallback_is_disabled_unless_explicitly_enabled():
    with (
        patch("app.services.meta_whatsapp_service.supabase_client", None),
        patch.object(settings, "META_WHATSAPP_PHONE_NUMBER_ID", "phone-1"),
        patch.object(settings, "META_WHATSAPP_DEFAULT_SHOP_ID", "shop-1"),
        patch.object(
            settings, "META_WHATSAPP_ALLOW_DEFAULT_CONNECTION_FALLBACK", False
        ),
    ):
        assert meta_whatsapp_service.resolve_connection("phone-1") is None
        fallback = meta_whatsapp_service.resolve_connection(
            "phone-1", allow_default=True
        )

    assert fallback["shop_id"] == "shop-1"
    assert fallback["token_reference"] == "env:META_WHATSAPP_ACCESS_TOKEN"


def test_status_callback_updates_existing_outbound_message():
    database = MagicMock()
    table = MagicMock()
    table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "outbound-1"}]
    )
    table.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "outbound-1"}]
    )
    database.table.return_value = table
    connection = {
        "id": "connection-1",
        "shop_id": "shop-1",
        "phone_number_id": "phone-1",
    }

    with patch("app.services.meta_whatsapp_service.supabase_client", database):
        meta_whatsapp_service.process_status(
            connection,
            {"id": "wamid-out", "status": "delivered", "timestamp": "1720000000"},
        )

    updates = table.update.call_args.args[0]
    assert updates["delivery_status"] == "delivered"
    assert updates["delivered_at"].endswith("+00:00")


async def _process_failed_event(attempts):
    event = {
        "id": "event-1",
        "connection_id": "connection-1",
        "phone_number_id": "phone-1",
        "event_kind": "message",
        "attempts": attempts,
        "max_attempts": 2,
        "payload": {"message": {"from": "919012345678"}},
    }
    connection = {
        "id": "connection-1",
        "shop_id": "shop-1",
        "phone_number_id": "phone-1",
    }
    with (
        patch.object(
            meta_whatsapp_service, "resolve_connection", return_value=connection
        ),
        patch.object(
            meta_whatsapp_service,
            "process_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("temporary failure"),
        ),
        patch.object(
            meta_whatsapp_service,
            "send_text",
            new_callable=AsyncMock,
            return_value={"sent": True},
        ) as send_text,
        patch.object(meta_whatsapp_event_service, "_mark_failed") as mark_failed,
        patch.object(meta_whatsapp_event_service, "_record_connection_failure"),
    ):
        mark_failed.return_value = attempts >= 2
        await meta_whatsapp_event_service.process_claimed_event(event)
        return send_text.await_count


@pytest.mark.asyncio
async def test_customer_failure_reply_is_sent_only_after_final_retry():
    assert await _process_failed_event(attempts=1) == 0
    assert await _process_failed_event(attempts=2) == 1


def test_meta_freeform_messages_are_limited_to_customer_service_window():
    now = datetime.datetime.now(datetime.timezone.utc)
    assert _meta_freeform_window_is_open(
        {
            "metadata": {
                "last_inbound_at": (
                    now - datetime.timedelta(hours=1)
                ).isoformat()
            }
        }
    )
    assert not _meta_freeform_window_is_open(
        {"last_inbound_at": (now - datetime.timedelta(hours=25)).isoformat()}
    )
    assert not _meta_freeform_window_is_open({})
