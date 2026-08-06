import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config.settings import settings
from app.main import app
from app.services.credential_cipher import telegram_credential_cipher
from app.services.telegram_connection_service import telegram_connection_service
from app.services.telegram_service import telegram_service


client = TestClient(app)


def _connection(connection_id="connection-1", shop_id="shop-1"):
    secret = "telegram-webhook-secret"
    return {
        "id": connection_id,
        "shop_id": shop_id,
        "status": "active",
        "webhook_secret_hash": telegram_connection_service._secret_hash(secret),
    }, secret


def test_telegram_credentials_are_encrypted_with_provider_namespace():
    key = base64.urlsafe_b64encode(b"t" * 32).decode()
    with patch.object(settings, "INTEGRATION_CREDENTIAL_ENCRYPTION_KEY", key):
        encrypted = telegram_credential_cipher.encrypt(
            "11111111-1111-1111-1111-111111111111", "bot-secret-token"
        )
        assert "bot-secret-token" not in encrypted["encrypted_token"]
        assert (
            telegram_credential_cipher.decrypt(
                "11111111-1111-1111-1111-111111111111", encrypted
            )
            == "bot-secret-token"
        )


def test_active_bot_cannot_be_connected_to_another_shop():
    database = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.execute.return_value = MagicMock(
        data=[{"id": "connection-a", "shop_id": "shop-a", "status": "active"}]
    )
    database.table.return_value = query
    with patch(
        "app.services.telegram_connection_service.supabase_client", database
    ):
        with pytest.raises(RuntimeError, match="TelegramBotAlreadyConnected"):
            telegram_connection_service._assert_bot_available("shop-b", "bot-1")


@pytest.mark.asyncio
async def test_connect_validates_bot_encrypts_token_and_registers_webhook():
    database = MagicMock()
    connection_table = MagicMock()
    credential_table = MagicMock()
    audit_table = MagicMock()
    connection_table.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "connection-1"}]
    )
    connection_table.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "connection-1"}]
    )
    credential_table.upsert.return_value.execute.return_value = MagicMock(data=[{}])
    audit_table.insert.return_value.execute.return_value = MagicMock(data=[{}])

    def table(name):
        return {
            "telegram_connections": connection_table,
            "telegram_connection_credentials": credential_table,
            "telegram_connection_audit_logs": audit_table,
        }[name]

    database.table.side_effect = table
    key = base64.urlsafe_b64encode(b"c" * 32).decode()
    telegram_request = AsyncMock(
        side_effect=[
            {"id": 12345, "is_bot": True, "username": "shop_bot", "first_name": "Shop"},
            True,
        ]
    )
    with (
        patch(
            "app.services.telegram_connection_service.supabase_client", database
        ),
        patch.object(settings, "INTEGRATION_CREDENTIAL_ENCRYPTION_KEY", key),
        patch.object(settings, "TELEGRAM_WEBHOOK_BASE_URL", "https://api.phoneerp.test"),
        patch.object(telegram_connection_service, "_telegram_request", telegram_request),
        patch.object(telegram_connection_service, "_shop_connection", return_value=None),
        patch.object(telegram_connection_service, "_assert_bot_available"),
        patch.object(
            telegram_connection_service,
            "get_status",
            return_value={"configured": True, "status": "active"},
        ),
    ):
        result = await telegram_connection_service.connect(
            "shop-1", "owner-1", "12345:secret", "https://fallback.test"
        )

    assert result["status"] == "active"
    encrypted = credential_table.upsert.call_args.args[0]
    assert "12345:secret" not in encrypted["encrypted_token"]
    webhook_call = telegram_request.await_args_list[1]
    assert webhook_call.args[1] == "setWebhook"
    assert webhook_call.args[2]["url"].startswith(
        "https://api.phoneerp.test/telegram/webhook/"
    )
    assert webhook_call.args[2]["secret_token"]


def test_connected_webhook_rejects_missing_or_invalid_secret():
    connection, _ = _connection()
    with patch.object(
        telegram_connection_service, "resolve_connection", return_value=connection
    ):
        missing = client.post(
            "/telegram/webhook/connection-1", json={"update_id": 1}
        )
        invalid = client.post(
            "/telegram/webhook/connection-1",
            json={"update_id": 2},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )
    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_connected_webhook_routes_only_mapped_connection():
    connection, secret = _connection()
    with (
        patch.object(
            telegram_connection_service, "resolve_connection", return_value=connection
        ),
        patch.object(telegram_connection_service, "mark_webhook_received") as marked,
        patch.object(
            telegram_service, "process_update", new_callable=AsyncMock
        ) as process_update,
    ):
        response = client.post(
            "/telegram/webhook/connection-1",
            json={"update_id": 10, "message": {"text": "hello"}},
            headers={"X-Telegram-Bot-Api-Secret-Token": secret},
        )
    assert response.status_code == 200
    marked.assert_called_once_with("connection-1")
    process_update.assert_awaited_once_with(
        {"update_id": 10, "message": {"text": "hello"}},
        connection=connection,
    )


@pytest.mark.asyncio
async def test_scoped_conversation_state_updates_customer_channel():
    connection, _ = _connection()
    customer = {
        "id": "customer-1",
        "telegram_state": "awaiting_name",
        "profile_completed": False,
        "_telegram_channel_id": "channel-1",
    }
    with (
        patch.object(
            telegram_service,
            "_resolve_connection_context",
            return_value=("shop-1", "owner-1", "bot-token"),
        ),
        patch.object(
            telegram_service, "get_or_create_customer", return_value=customer
        ) as get_customer,
        patch.object(telegram_service, "update_customer") as update_customer,
        patch.object(telegram_service, "send_message"),
    ):
        await telegram_service.process_update(
            {
                "message": {
                    "message_id": 7,
                    "chat": {"id": 123},
                    "from": {"id": 456},
                    "text": "Danish",
                }
            },
            connection=connection,
        )
    get_customer.assert_called_once_with("456", "123", shop_id="shop-1")
    update_customer.assert_called_once_with(
        "customer-1",
        {"name": "Danish", "telegram_state": "awaiting_address"},
        channel_id="channel-1",
    )


@pytest.mark.asyncio
async def test_provider_message_id_is_namespaced_by_bot_connection():
    connection, _ = _connection()
    customer = {
        "id": "customer-1",
        "telegram_state": "ready",
        "profile_completed": True,
        "_telegram_channel_id": "channel-1",
    }
    with (
        patch.object(
            telegram_service,
            "_resolve_connection_context",
            return_value=("shop-1", "owner-1", "bot-token"),
        ),
        patch.object(
            telegram_service, "get_or_create_customer", return_value=customer
        ),
        patch.object(telegram_service, "send_message"),
        patch(
            "app.services.intent_router.IntentRouter.process_inbound_message",
            new_callable=AsyncMock,
            return_value={"status": "processed"},
        ) as process_message,
    ):
        await telegram_service.process_update(
            {
                "message": {
                    "message_id": 9,
                    "chat": {"id": 123},
                    "from": {"id": 456},
                    "text": "5 kilo aata bhej dena",
                }
            },
            connection=connection,
        )
    normalized = process_message.await_args.args[0]
    assert normalized.shop_id == "shop-1"
    assert normalized.provider_message_id == "connection-1:123:9"
    assert normalized.metadata["telegram_connection_id"] == "connection-1"
