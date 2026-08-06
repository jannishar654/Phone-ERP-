import datetime
import hashlib
import hmac
import logging
import secrets
import uuid
from typing import Any, Dict, Optional

import httpx

from app.config.settings import settings
from app.services.credential_cipher import telegram_credential_cipher
from app.services.supabase import supabase_client


logger = logging.getLogger(__name__)


class TelegramConnectionService:
    API_ROOT = "https://api.telegram.org"

    @staticmethod
    def _require_database() -> None:
        if not supabase_client:
            raise RuntimeError("DatabaseUnavailable")

    @staticmethod
    def _secret_hash(secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    @staticmethod
    def _safe_bot_name(bot: Dict[str, Any]) -> str:
        return " ".join(
            part for part in [bot.get("first_name"), bot.get("last_name")] if part
        ).strip()

    @staticmethod
    def _webhook_url(connection_id: str, base_url: str) -> str:
        configured = settings.TELEGRAM_WEBHOOK_BASE_URL.strip()
        origin = (configured or base_url).rstrip("/")
        if not origin.startswith("https://") and settings.ENVIRONMENT == "production":
            raise RuntimeError("TelegramWebhookUrlInvalid")
        return f"{origin}/telegram/webhook/{connection_id}"

    async def _telegram_request(
        self, token: str, method: str, payload: Optional[dict] = None
    ) -> dict:
        url = f"{self.API_ROOT}/bot{token}/{method}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload or {})
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError("TelegramInvalidResponse") from exc
        if response.status_code >= 400 or not body.get("ok"):
            logger.warning(
                "Telegram API request failed method=%s status=%s error_code=%s",
                method,
                response.status_code,
                body.get("error_code"),
            )
            if response.status_code in {401, 404}:
                raise RuntimeError("TelegramTokenInvalid")
            raise RuntimeError("TelegramApiRequestFailed")
        return body.get("result")

    def _audit(
        self,
        shop_id: str,
        action: str,
        user_id: Optional[str],
        connection_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        try:
            supabase_client.table("telegram_connection_audit_logs").insert(
                {
                    "shop_id": shop_id,
                    "connection_id": connection_id,
                    "actor_user_id": user_id,
                    "action": action,
                    "safe_metadata": metadata or {},
                }
            ).execute()
        except Exception as exc:
            logger.warning(
                "Telegram integration audit failed action=%s error_type=%s",
                action,
                type(exc).__name__,
            )

    def _shop_connection(self, shop_id: str) -> Optional[dict]:
        self._require_database()
        result = (
            supabase_client.table("telegram_connections")
            .select("*")
            .eq("shop_id", shop_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def resolve_connection(self, connection_id: str) -> Optional[dict]:
        if not supabase_client:
            return None
        result = (
            supabase_client.table("telegram_connections")
            .select("*")
            .eq("id", connection_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def resolve_shop_connection(self, shop_id: str) -> Optional[dict]:
        if not supabase_client:
            return None
        result = (
            supabase_client.table("telegram_connections")
            .select("*")
            .eq("shop_id", shop_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def resolve_token(self, connection: dict) -> str:
        connection_id = str(connection.get("id") or "")
        if not connection_id or connection.get("token_reference") != f"db:{connection_id}":
            raise RuntimeError("TelegramCredentialReferenceInvalid")
        result = (
            supabase_client.table("telegram_connection_credentials")
            .select("encrypted_token, token_nonce, key_version")
            .eq("connection_id", connection_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise RuntimeError("TelegramCredentialMissing")
        return telegram_credential_cipher.decrypt(connection_id, result.data[0])

    def verify_webhook_secret(self, connection: dict, provided: str) -> bool:
        expected = str(connection.get("webhook_secret_hash") or "")
        actual = self._secret_hash(provided) if provided else ""
        return bool(expected and hmac.compare_digest(expected, actual))

    def mark_webhook_received(self, connection_id: str) -> None:
        if not supabase_client:
            return
        supabase_client.table("telegram_connections").update(
            {"last_webhook_at": self._now(), "last_error": None}
        ).eq("id", connection_id).execute()

    def get_status(self, shop_id: str) -> dict:
        connection = self._shop_connection(shop_id)
        configured = bool(
            settings.INTEGRATION_CREDENTIAL_ENCRYPTION_KEY
            or settings.META_WHATSAPP_TOKEN_ENCRYPTION_KEY
        )
        if not connection:
            return {"configured": configured, "status": "not_connected"}
        return {
            "configured": configured,
            "status": connection.get("status") or "error",
            "bot_id": connection.get("bot_id"),
            "bot_username": connection.get("bot_username"),
            "bot_display_name": connection.get("bot_display_name"),
            "last_webhook_at": connection.get("last_webhook_at"),
            "last_health_check_at": connection.get("last_health_check_at"),
            "last_error": connection.get("last_error"),
            "connected_at": connection.get("connected_at"),
        }

    def _assert_bot_available(self, shop_id: str, bot_id: str) -> None:
        result = (
            supabase_client.table("telegram_connections")
            .select("id, shop_id, status")
            .eq("bot_id", bot_id)
            .execute()
        )
        for row in result.data or []:
            if row.get("shop_id") == shop_id:
                continue
            if row.get("status") != "disconnected":
                raise RuntimeError("TelegramBotAlreadyConnected")
            supabase_client.table("telegram_connections").delete().eq(
                "id", row["id"]
            ).execute()

    async def connect(
        self, shop_id: str, user_id: str, bot_token: str, base_url: str
    ) -> dict:
        self._require_database()
        token = bot_token.strip()
        if not token or len(token) > 512:
            raise RuntimeError("TelegramTokenInvalid")

        bot = await self._telegram_request(token, "getMe")
        if not isinstance(bot, dict) or not bot.get("is_bot") or not bot.get("id"):
            raise RuntimeError("TelegramTokenInvalid")
        bot_id = str(bot["id"])
        self._assert_bot_available(shop_id, bot_id)

        existing = self._shop_connection(shop_id)
        if existing and existing.get("status") in {"active", "pending"}:
            raise RuntimeError("DisconnectCurrentBotFirst")

        connection_id = str(existing.get("id")) if existing else str(uuid.uuid4())
        webhook_secret = secrets.token_urlsafe(32).replace(".", "_")[:64]
        now = self._now()
        payload = {
            "shop_id": shop_id,
            "bot_id": bot_id,
            "bot_username": bot.get("username"),
            "bot_display_name": self._safe_bot_name(bot),
            "status": "pending",
            "token_reference": f"db:{connection_id}",
            "webhook_secret_hash": self._secret_hash(webhook_secret),
            "connected_by": user_id,
            "disconnected_by": None,
            "disconnected_at": None,
            "last_error": None,
        }
        if existing:
            result = (
                supabase_client.table("telegram_connections")
                .update(payload)
                .eq("id", connection_id)
                .execute()
            )
        else:
            result = supabase_client.table("telegram_connections").insert(
                {"id": connection_id, **payload}
            ).execute()
        if not result.data:
            raise RuntimeError("TelegramConnectionSaveFailed")

        encrypted = telegram_credential_cipher.encrypt(connection_id, token)
        supabase_client.table("telegram_connection_credentials").upsert(
            encrypted, on_conflict="connection_id"
        ).execute()

        webhook_url = self._webhook_url(connection_id, base_url)
        try:
            await self._telegram_request(
                token,
                "setWebhook",
                {
                    "url": webhook_url,
                    "secret_token": webhook_secret,
                    "allowed_updates": ["message"],
                    "drop_pending_updates": False,
                },
            )
        except Exception as exc:
            supabase_client.table("telegram_connections").update(
                {"status": "error", "last_error": str(exc)[:160]}
            ).eq("id", connection_id).execute()
            self._audit(shop_id, "connect_failed", user_id, connection_id)
            raise

        supabase_client.table("telegram_connections").update(
            {
                "status": "active",
                "connected_at": now,
                "last_health_check_at": now,
                "last_error": None,
            }
        ).eq("id", connection_id).execute()
        self._audit(
            shop_id,
            "connected",
            user_id,
            connection_id,
            {"bot_id": bot_id, "bot_username": bot.get("username")},
        )
        return self.get_status(shop_id)

    async def health_check(self, shop_id: str, user_id: str, base_url: str) -> dict:
        connection = self._shop_connection(shop_id)
        if not connection or connection.get("status") != "active":
            raise RuntimeError("NoActiveTelegramConnection")
        token = self.resolve_token(connection)
        try:
            bot = await self._telegram_request(token, "getMe")
            webhook = await self._telegram_request(token, "getWebhookInfo")
            expected_url = self._webhook_url(str(connection["id"]), base_url)
            if not isinstance(webhook, dict) or webhook.get("url") != expected_url:
                raise RuntimeError("TelegramWebhookMismatch")
            now = self._now()
            supabase_client.table("telegram_connections").update(
                {"last_health_check_at": now, "last_error": None}
            ).eq("id", connection["id"]).execute()
            return {
                "healthy": True,
                "status": "active",
                "bot_username": bot.get("username") if isinstance(bot, dict) else None,
                "pending_update_count": int(webhook.get("pending_update_count") or 0),
            }
        except Exception as exc:
            supabase_client.table("telegram_connections").update(
                {
                    "last_health_check_at": self._now(),
                    "last_error": str(exc)[:160],
                }
            ).eq("id", connection["id"]).execute()
            self._audit(shop_id, "health_check_failed", user_id, connection["id"])
            raise

    async def disconnect(self, shop_id: str, user_id: str) -> None:
        connection = self._shop_connection(shop_id)
        if not connection or connection.get("status") == "disconnected":
            raise RuntimeError("NoActiveTelegramConnection")
        try:
            token = self.resolve_token(connection)
            await self._telegram_request(
                token, "deleteWebhook", {"drop_pending_updates": False}
            )
        except Exception as exc:
            logger.warning(
                "Telegram webhook removal failed connection_id=%s error_type=%s",
                connection.get("id"),
                type(exc).__name__,
            )
        supabase_client.table("telegram_connection_credentials").delete().eq(
            "connection_id", connection["id"]
        ).execute()
        supabase_client.table("telegram_connections").update(
            {
                "status": "disconnected",
                "token_reference": None,
                "disconnected_by": user_id,
                "disconnected_at": self._now(),
            }
        ).eq("id", connection["id"]).execute()
        self._audit(shop_id, "disconnected", user_id, connection["id"])


telegram_connection_service = TelegramConnectionService()
