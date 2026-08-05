import base64
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.config.settings import settings
from app.schemas.whatsapp_integration import WhatsAppOnboardingCallbackRequest
from app.services.credential_cipher import credential_cipher
from app.services.meta_whatsapp_onboarding_service import (
    meta_whatsapp_onboarding_service,
)
from app.services.meta_whatsapp_service import meta_whatsapp_service


def _enabled_settings():
    return (
        patch.object(settings, "META_WHATSAPP_EMBEDDED_SIGNUP_ENABLED", True),
        patch.object(
            settings,
            "META_WHATSAPP_EMBEDDED_SIGNUP_ALLOWED_SHOP_IDS",
            ["shop-1"],
        ),
        patch.object(settings, "META_APP_ID", "app-1"),
        patch.object(settings, "META_APP_SECRET", "app-secret"),
        patch.object(
            settings, "META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID", "config-1"
        ),
        patch.object(
            settings,
            "META_WHATSAPP_TOKEN_ENCRYPTION_KEY",
            base64.urlsafe_b64encode(b"k" * 32).decode(),
        ),
    )


def test_credential_cipher_round_trip_and_tamper_detection():
    with patch.object(
        settings,
        "META_WHATSAPP_TOKEN_ENCRYPTION_KEY",
        base64.urlsafe_b64encode(b"a" * 32).decode(),
    ):
        encrypted = credential_cipher.encrypt(
            "11111111-1111-1111-1111-111111111111", "tenant-secret-token"
        )
        assert "tenant-secret-token" not in encrypted["encrypted_token"]
        assert (
            credential_cipher.decrypt(
                "11111111-1111-1111-1111-111111111111", encrypted
            )
            == "tenant-secret-token"
        )
        encrypted["encrypted_token"] = encrypted["encrypted_token"][:-2] + "AA"
        with pytest.raises(RuntimeError, match="could not be decrypted"):
            credential_cipher.decrypt(
                "11111111-1111-1111-1111-111111111111", encrypted
            )


def test_registration_pin_is_validated_and_kept_secret():
    callback = WhatsAppOnboardingCallbackRequest(
        state="s" * 32,
        code="authorization-code",
        registration_pin="123456",
    )
    assert callback.registration_pin.get_secret_value() == "123456"
    assert "123456" not in repr(callback)
    with pytest.raises(ValidationError):
        WhatsAppOnboardingCallbackRequest(
            state="s" * 32,
            code="authorization-code",
            registration_pin="12ab56",
        )


def test_onboarding_session_stores_only_state_hash():
    database = MagicMock()
    session_table = MagicMock()
    session_table.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "session-1"}]
    )
    audit_table = MagicMock()
    audit_table.insert.return_value.execute.return_value = MagicMock(data=[{}])
    database.table.side_effect = lambda name: (
        session_table if name == "whatsapp_onboarding_sessions" else audit_table
    )
    with ExitStack() as stack:
        for setting_patch in _enabled_settings():
            stack.enter_context(setting_patch)
        stack.enter_context(
            patch(
                "app.services.meta_whatsapp_onboarding_service.supabase_client",
                database,
            )
        )
        result = meta_whatsapp_onboarding_service.create_session("user-1", "shop-1")

    inserted = session_table.insert.call_args.args[0]
    assert result["state"]
    assert inserted["state_hash"] != result["state"]
    assert len(inserted["state_hash"]) == 64
    assert "state" not in inserted


@pytest.mark.asyncio
async def test_selected_phone_must_belong_to_granted_waba():
    request = AsyncMock(
        return_value={
            "data": [
                {
                    "id": "phone-granted",
                    "display_phone_number": "+91 90000 00000",
                }
            ]
        }
    )
    with patch.object(meta_whatsapp_onboarding_service, "_request", request):
        with pytest.raises(RuntimeError, match="PhoneNotGranted"):
            await meta_whatsapp_onboarding_service._select_assets(
                "token",
                {"waba-granted"},
                "waba-granted",
                "phone-from-frontend-but-not-granted",
            )

        with pytest.raises(RuntimeError, match="WabaNotGranted"):
            await meta_whatsapp_onboarding_service._select_assets(
                "token", {"waba-granted"}, "waba-attacker", None
            )


@pytest.mark.asyncio
async def test_phone_registration_sends_required_meta_payload():
    request = AsyncMock(return_value={"success": True})
    with patch.object(meta_whatsapp_onboarding_service, "_request", request):
        await meta_whatsapp_onboarding_service._register_phone(
            "business-token", "phone-1", "123456"
        )
    request.assert_awaited_once_with(
        "POST",
        meta_whatsapp_onboarding_service._graph_url("phone-1/register"),
        token="business-token",
        json={"messaging_product": "whatsapp", "pin": "123456"},
    )


def test_phone_number_cannot_be_connected_to_another_shop():
    database = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.in_.return_value = query
    query.execute.return_value = MagicMock(
        data=[{"id": "connection-1", "shop_id": "shop-a", "status": "active"}]
    )
    database.table.return_value = query
    with patch(
        "app.services.meta_whatsapp_onboarding_service.supabase_client", database
    ):
        with pytest.raises(RuntimeError, match="PhoneAlreadyConnected"):
            meta_whatsapp_onboarding_service._assert_phone_available(
                "shop-b", "phone-1"
            )


def test_waba_cannot_be_connected_to_another_shop():
    database = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.in_.return_value = query
    query.execute.return_value = MagicMock(
        data=[{"id": "connection-1", "shop_id": "shop-a", "status": "active"}]
    )
    database.table.return_value = query
    with patch(
        "app.services.meta_whatsapp_onboarding_service.supabase_client", database
    ):
        with pytest.raises(RuntimeError, match="WabaAlreadyConnected"):
            meta_whatsapp_onboarding_service._assert_waba_available(
                "shop-b", "waba-1"
            )


def test_meta_service_resolves_encrypted_database_credential():
    connection_id = "22222222-2222-2222-2222-222222222222"
    with patch.object(
        settings,
        "META_WHATSAPP_TOKEN_ENCRYPTION_KEY",
        base64.urlsafe_b64encode(b"b" * 32).decode(),
    ):
        encrypted = credential_cipher.encrypt(connection_id, "business-token")
        database = MagicMock()
        query = MagicMock()
        query.select.return_value = query
        query.eq.return_value = query
        query.limit.return_value = query
        query.execute.return_value = MagicMock(data=[encrypted])
        database.table.return_value = query
        with patch(
            "app.services.meta_whatsapp_service.supabase_client", database
        ):
            token = meta_whatsapp_service._resolve_access_token(
                {"id": connection_id, "token_reference": f"db:{connection_id}"}
            )
    assert token == "business-token"


def test_embedded_signup_is_off_by_default():
    with patch.object(settings, "META_WHATSAPP_EMBEDDED_SIGNUP_ENABLED", False):
        with pytest.raises(RuntimeError, match="EmbeddedSignupDisabled"):
            meta_whatsapp_onboarding_service.create_session("user-1", "shop-1")


def test_embedded_signup_rejects_shop_outside_pilot_allowlist():
    with patch.object(settings, "META_WHATSAPP_EMBEDDED_SIGNUP_ENABLED", True), patch.object(
        settings, "META_WHATSAPP_EMBEDDED_SIGNUP_ALLOWED_SHOP_IDS", ["shop-allowed"]
    ):
        with pytest.raises(RuntimeError, match="EmbeddedSignupDisabled"):
            meta_whatsapp_onboarding_service.create_session("user-1", "shop-other")
