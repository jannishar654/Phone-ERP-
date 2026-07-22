import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config.settings import settings
from app.main import app
from app.services.meta_whatsapp_event_service import meta_whatsapp_event_service
from app.services.meta_whatsapp_service import meta_whatsapp_service


client = TestClient(app)


def _signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


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


def test_webhook_verification_returns_meta_challenge():
    with patch.object(settings, "META_WHATSAPP_VERIFY_TOKEN", "verify-secret"):
        response = client.get(
            "/meta/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-secret",
                "hub.challenge": "123456",
            },
        )
    assert response.status_code == 200
    assert response.text == "123456"


def test_webhook_verification_rejects_wrong_token():
    with patch.object(settings, "META_WHATSAPP_VERIFY_TOKEN", "verify-secret"):
        response = client.get(
            "/meta/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong",
                "hub.challenge": "123456",
            },
        )
    assert response.status_code == 403


def test_webhook_rejects_invalid_signature():
    with patch.object(settings, "META_APP_SECRET", "app-secret"):
        response = client.post(
            "/meta/whatsapp/webhook",
            json=_message_payload(),
            headers={"X-Hub-Signature-256": "sha256=wrong"},
        )
    assert response.status_code == 403


def test_signed_message_webhook_queues_existing_pipeline():
    body = json.dumps(_message_payload(), separators=(",", ":")).encode()
    with (
        patch.object(settings, "META_APP_SECRET", "app-secret"),
        patch.object(
            meta_whatsapp_event_service,
            "persist_webhook_payload",
            return_value=["event-1"],
        ) as persist_webhook,
        patch.object(
            meta_whatsapp_event_service, "process_event", new_callable=AsyncMock
        ) as process_event,
    ):
        response = client.post(
            "/meta/whatsapp/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _signature(body, "app-secret"),
            },
        )

    assert response.status_code == 200
    assert response.json() == {"received": True, "queued": 1}
    persist_webhook.assert_called_once_with(_message_payload())
    process_event.assert_awaited_once_with("event-1")


def test_status_only_webhook_is_persisted_and_queued():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "phone-1"},
                            "statuses": [{"id": "wamid-out", "status": "delivered"}],
                        },
                    }
                ]
            }
        ],
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    with (
        patch.object(settings, "META_APP_SECRET", "app-secret"),
        patch.object(
            meta_whatsapp_event_service,
            "persist_webhook_payload",
            return_value=["status-event-1"],
        ),
        patch.object(
            meta_whatsapp_event_service, "process_event", new_callable=AsyncMock
        ) as process_event,
    ):
        response = client.post(
            "/meta/whatsapp/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _signature(body, "app-secret"),
            },
        )

    assert response.status_code == 200
    assert response.json()["queued"] == 1
    process_event.assert_awaited_once_with("status-event-1")


def test_webhook_returns_retryable_error_when_persistence_fails():
    body = json.dumps(_message_payload(), separators=(",", ":")).encode()
    with (
        patch.object(settings, "META_APP_SECRET", "app-secret"),
        patch.object(
            meta_whatsapp_event_service,
            "persist_webhook_payload",
            side_effect=RuntimeError("database unavailable"),
        ),
    ):
        response = client.post(
            "/meta/whatsapp/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _signature(body, "app-secret"),
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Webhook persistence is temporarily unavailable"


def test_webhook_rejects_oversized_payload_before_processing():
    body = json.dumps(_message_payload(), separators=(",", ":")).encode()
    with (
        patch.object(settings, "META_APP_SECRET", "app-secret"),
        patch.object(settings, "META_WHATSAPP_MAX_WEBHOOK_BYTES", len(body) - 1),
    ):
        response = client.post(
            "/meta/whatsapp/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _signature(body, "app-secret"),
            },
        )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_text_message_uses_normalized_intent_pipeline():
    channel = {"customer_id": "customer-1", "customers": {"id": "customer-1"}}
    router_result = {"status": "processed", "reply_message": "Order received"}
    with (
        patch.object(
            meta_whatsapp_service,
            "resolve_connection",
            return_value={
                "shop_id": "shop-1",
                "waba_id": "waba-1",
                "phone_number_id": "phone-1",
            },
        ),
        patch.object(
            meta_whatsapp_service, "get_or_create_customer", return_value=channel
        ),
        patch(
            "app.services.meta_whatsapp_service.IntentRouter.process_inbound_message",
            new_callable=AsyncMock,
            return_value=router_result,
        ) as process_inbound,
        patch.object(
            meta_whatsapp_service,
            "send_text",
            new_callable=AsyncMock,
            return_value={"sent": True},
        ) as send_text,
    ):
        await meta_whatsapp_service.process_message(
            "phone-1",
            {
                "id": "wamid-1",
                "from": "919012345678",
                "type": "text",
                "text": {"body": "kal 5 kilo aata bhej dena"},
            },
            {"wa_id": "919012345678", "profile": {"name": "Danish"}},
        )

    inbound = process_inbound.await_args.args[0]
    assert inbound.shop_id == "shop-1"
    assert inbound.channel.value == "meta_whatsapp"
    assert inbound.provider_message_id == "wamid-1"
    assert inbound.raw_text == "kal 5 kilo aata bhej dena"
    send_text.assert_awaited_once_with(
        "919012345678", "Order received", "phone-1"
    )
