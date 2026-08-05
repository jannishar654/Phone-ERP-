import datetime
import hashlib
import logging
import secrets
from typing import Any, Dict, Iterable, Optional

import httpx

from app.config.settings import settings
from app.services.credential_cipher import credential_cipher
from app.services.supabase import supabase_client


logger = logging.getLogger(__name__)


class MetaWhatsAppOnboardingService:
    SESSION_TTL_SECONDS = 10 * 60
    REQUIRED_SCOPES = {
        "business_management",
        "whatsapp_business_management",
        "whatsapp_business_messaging",
    }

    def _graph_url(self, path: str) -> str:
        version = settings.META_GRAPH_API_VERSION.strip("/") or "v25.0"
        return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"

    @staticmethod
    def _state_hash(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    @staticmethod
    def _require_database() -> None:
        if not supabase_client:
            raise RuntimeError("DatabaseUnavailable")

    @staticmethod
    def _is_configured() -> bool:
        return all(
            [
                settings.META_APP_ID,
                settings.META_APP_SECRET,
                settings.META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID,
                settings.META_WHATSAPP_TOKEN_ENCRYPTION_KEY,
            ]
        )

    @staticmethod
    def _is_enabled_for_shop(shop_id: str) -> bool:
        allowed = set(settings.META_WHATSAPP_EMBEDDED_SIGNUP_ALLOWED_SHOP_IDS)
        return settings.META_WHATSAPP_EMBEDDED_SIGNUP_ENABLED and (
            "*" in allowed or shop_id in allowed
        )

    def _require_enabled(self, shop_id: str) -> None:
        if not self._is_enabled_for_shop(shop_id):
            raise RuntimeError("EmbeddedSignupDisabled")
        if not self._is_configured():
            raise RuntimeError("EmbeddedSignupNotConfigured")
        self._require_database()

    def _audit(
        self,
        shop_id: str,
        action: str,
        user_id: Optional[str],
        connection_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            supabase_client.table("whatsapp_connection_audit_logs").insert(
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
                "WhatsApp onboarding audit failed action=%s error_type=%s",
                action,
                type(exc).__name__,
            )

    def create_session(self, user_id: str, shop_id: str) -> Dict[str, Any]:
        self._require_enabled(shop_id)
        state = secrets.token_urlsafe(48)
        expires_at = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(seconds=self.SESSION_TTL_SECONDS)
        result = supabase_client.table("whatsapp_onboarding_sessions").insert(
            {
                "state_hash": self._state_hash(state),
                "user_id": user_id,
                "shop_id": shop_id,
                "expires_at": expires_at.isoformat(),
            }
        ).execute()
        if not result.data:
            raise RuntimeError("OnboardingSessionCreateFailed")
        self._audit(shop_id, "onboarding_started", user_id)
        return {
            "state": state,
            "app_id": settings.META_APP_ID,
            "configuration_id": settings.META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID,
            "graph_api_version": settings.META_GRAPH_API_VERSION,
            "expires_in_seconds": self.SESSION_TTL_SECONDS,
        }

    def _consume_session(self, state: str, user_id: str, shop_id: str) -> dict:
        result = supabase_client.rpc(
            "consume_whatsapp_onboarding_session",
            {
                "p_state_hash": self._state_hash(state),
                "p_user_id": user_id,
                "p_shop_id": shop_id,
            },
        ).execute()
        if not result.data:
            raise RuntimeError("InvalidOrExpiredOnboardingSession")
        return result.data[0]

    async def _request(
        self,
        method: str,
        url: str,
        *,
        token: Optional[str] = None,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
            )
        if response.status_code >= 400:
            logger.warning(
                "Meta onboarding Graph request failed status=%s path=%s",
                response.status_code,
                url.rsplit("/", 1)[-1].split("?", 1)[0],
            )
            raise RuntimeError("MetaGraphRequestFailed")
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("MetaGraphInvalidResponse") from exc

    async def _exchange_code(self, code: str) -> Dict[str, Any]:
        data = await self._request(
            "GET",
            self._graph_url("oauth/access_token"),
            params={
                "client_id": settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "code": code,
            },
        )
        token = data.get("access_token")
        if not token:
            raise RuntimeError("MetaCodeExchangeFailed")
        return data

    async def _debug_token(self, token: str) -> Dict[str, Any]:
        app_token = f"{settings.META_APP_ID}|{settings.META_APP_SECRET}"
        payload = await self._request(
            "GET",
            self._graph_url("debug_token"),
            token=app_token,
            params={"input_token": token},
        )
        data = payload.get("data") or {}
        scopes = set(data.get("scopes") or [])
        if not data.get("is_valid") or str(data.get("app_id")) != settings.META_APP_ID:
            raise RuntimeError("MetaTokenValidationFailed")
        if not self.REQUIRED_SCOPES.issubset(scopes):
            raise RuntimeError("MetaPermissionsMissing")
        return data

    @staticmethod
    def _granted_waba_ids(debug_data: dict) -> set[str]:
        ids: set[str] = set()
        for scope in debug_data.get("granular_scopes") or []:
            if scope.get("scope") == "whatsapp_business_management":
                ids.update(str(value) for value in scope.get("target_ids") or [])
        return ids

    async def _select_assets(
        self,
        token: str,
        granted_waba_ids: Iterable[str],
        waba_hint: Optional[str],
        phone_hint: Optional[str],
    ) -> tuple[str, dict]:
        candidates = set(granted_waba_ids)
        if waba_hint:
            if waba_hint not in candidates:
                raise RuntimeError("WabaNotGranted")
            candidates = {waba_hint}
        if not candidates:
            raise RuntimeError("NoGrantedWaba")

        matches: list[tuple[str, dict]] = []
        for waba_id in candidates:
            payload = await self._request(
                "GET",
                self._graph_url(f"{waba_id}/phone_numbers"),
                token=token,
                params={
                    "fields": "id,display_phone_number,verified_name,quality_rating,status"
                },
            )
            for phone in payload.get("data") or []:
                if phone_hint and str(phone.get("id")) != phone_hint:
                    continue
                matches.append((waba_id, phone))

        if len(matches) != 1:
            raise RuntimeError(
                "PhoneSelectionRequired" if matches else "PhoneNotGranted"
            )
        return matches[0]

    async def _register_phone(
        self, token: str, phone_number_id: str, registration_pin: str
    ) -> None:
        await self._request(
            "POST",
            self._graph_url(f"{phone_number_id}/register"),
            token=token,
            json={
                "messaging_product": "whatsapp",
                "pin": registration_pin,
            },
        )

    def _assert_phone_available(self, shop_id: str, phone_number_id: str) -> None:
        result = (
            supabase_client.table("whatsapp_connections")
            .select("id,shop_id,status")
            .eq("provider", "meta_cloud")
            .eq("phone_number_id", phone_number_id)
            .in_("status", ["pending", "active", "reconnect_required"])
            .execute()
        )
        if any(row.get("shop_id") != shop_id for row in result.data or []):
            raise RuntimeError("PhoneAlreadyConnected")

    def _assert_waba_available(self, shop_id: str, waba_id: str) -> None:
        result = (
            supabase_client.table("whatsapp_connections")
            .select("id,shop_id,status")
            .eq("provider", "meta_cloud")
            .eq("waba_id", waba_id)
            .in_("status", ["pending", "active", "reconnect_required", "error"])
            .execute()
        )
        if any(row.get("shop_id") != shop_id for row in result.data or []):
            raise RuntimeError("WabaAlreadyConnected")

    def _existing_connection(self, shop_id: str) -> Optional[dict]:
        result = (
            supabase_client.table("whatsapp_connections")
            .select("*")
            .eq("provider", "meta_cloud")
            .eq("shop_id", shop_id)
            .in_("status", ["pending", "active", "reconnect_required", "error"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    async def complete_onboarding(
        self,
        *,
        state: str,
        code: str,
        user_id: str,
        shop_id: str,
        waba_hint: Optional[str],
        phone_hint: Optional[str],
        registration_pin: str,
    ) -> dict:
        self._require_enabled(shop_id)
        session = self._consume_session(state, user_id, shop_id)
        connection_id: Optional[str] = None
        try:
            exchanged = await self._exchange_code(code)
            token = exchanged["access_token"]
            debug_data = await self._debug_token(token)
            waba_id, phone = await self._select_assets(
                token,
                self._granted_waba_ids(debug_data),
                waba_hint,
                phone_hint,
            )
            phone_number_id = str(phone["id"])
            self._assert_phone_available(shop_id, phone_number_id)
            self._assert_waba_available(shop_id, waba_id)
            # Meta business metadata is useful for support, but it is not part
            # of the security decision. Some granted tokens omit this optional
            # field, so onboarding must not fail when it is unavailable.
            owner_business: Dict[str, Any] = {}
            try:
                waba_info = await self._request(
                    "GET",
                    self._graph_url(waba_id),
                    token=token,
                    params={"fields": "id,name,owner_business_info"},
                )
                owner_business = waba_info.get("owner_business_info") or {}
            except RuntimeError:
                logger.info(
                    "Optional Meta business metadata unavailable waba_id=%s",
                    waba_id,
                )

            existing = self._existing_connection(shop_id)
            if existing and existing.get("status") == "active" and str(
                existing.get("phone_number_id")
            ) != phone_number_id:
                raise RuntimeError("DisconnectCurrentNumberFirst")

            expires_at = None
            expires_timestamp = debug_data.get("expires_at")
            if expires_timestamp:
                expires_at = datetime.datetime.fromtimestamp(
                    int(expires_timestamp), datetime.timezone.utc
                ).isoformat()
            connection_data = {
                "shop_id": shop_id,
                "provider": "meta_cloud",
                "meta_business_id": owner_business.get("id"),
                "waba_id": waba_id,
                "phone_number_id": phone_number_id,
                "display_phone_number": phone.get("display_phone_number"),
                "verified_name": phone.get("verified_name"),
                "status": "pending",
                "granted_scopes": sorted(debug_data.get("scopes") or []),
                "token_expires_at": expires_at,
                "connected_by": user_id,
                "last_error": None,
            }
            if existing:
                connection_id = existing["id"]
                saved = (
                    supabase_client.table("whatsapp_connections")
                    .update(connection_data)
                    .eq("id", connection_id)
                    .eq("shop_id", shop_id)
                    .execute()
                )
            else:
                saved = (
                    supabase_client.table("whatsapp_connections")
                    .insert(connection_data)
                    .execute()
                )
                if saved.data:
                    connection_id = saved.data[0]["id"]
            if not saved.data or not connection_id:
                raise RuntimeError("ConnectionSaveFailed")

            credential = credential_cipher.encrypt(connection_id, token)
            supabase_client.table("whatsapp_connection_credentials").upsert(
                credential, on_conflict="connection_id"
            ).execute()
            supabase_client.table("whatsapp_connections").update(
                {"token_reference": f"db:{connection_id}"}
            ).eq("id", connection_id).execute()

            await self._register_phone(token, phone_number_id, registration_pin)
            await self._request(
                "POST",
                self._graph_url(f"{waba_id}/subscribed_apps"),
                token=token,
            )
            health = await self._request(
                "GET",
                self._graph_url(phone_number_id),
                token=token,
                params={"fields": "id,display_phone_number,verified_name,quality_rating"},
            )
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            activated = (
                supabase_client.table("whatsapp_connections")
                .update(
                    {
                        "status": "active",
                        "connected_at": now,
                        "disconnected_at": None,
                        "last_health_check_at": now,
                        "failure_count": 0,
                        "last_error": None,
                        "display_phone_number": health.get("display_phone_number")
                        or phone.get("display_phone_number"),
                        "verified_name": health.get("verified_name")
                        or phone.get("verified_name"),
                    }
                )
                .eq("id", connection_id)
                .eq("shop_id", shop_id)
                .execute()
            )
            if not activated.data:
                raise RuntimeError("ConnectionActivationFailed")
            supabase_client.table("whatsapp_onboarding_sessions").update(
                {"status": "completed"}
            ).eq("id", session["id"]).execute()
            self._audit(
                shop_id,
                "connection_activated",
                user_id,
                connection_id,
                {"waba_id": waba_id, "phone_number_id": phone_number_id},
            )
            return activated.data[0]
        except Exception as exc:
            safe_code = str(exc) if isinstance(exc, RuntimeError) else "OnboardingFailed"
            supabase_client.table("whatsapp_onboarding_sessions").update(
                {"status": "failed", "safe_error_code": safe_code[:100]}
            ).eq("id", session["id"]).execute()
            if connection_id:
                supabase_client.table("whatsapp_connections").update(
                    {"status": "error", "last_error": safe_code[:200]}
                ).eq("id", connection_id).execute()
            self._audit(
                shop_id,
                "onboarding_failed",
                user_id,
                connection_id,
                {"error_code": safe_code[:100]},
            )
            raise

    def get_status(self, shop_id: str) -> Dict[str, Any]:
        self._require_database()
        connection = self._existing_connection(shop_id)
        base = {
            "embedded_signup_enabled": self._is_enabled_for_shop(shop_id),
            "configured": self._is_configured(),
            "status": "not_connected",
        }
        if not connection:
            return base
        for field in (
            "status",
            "display_phone_number",
            "verified_name",
            "waba_id",
            "phone_number_id",
            "last_webhook_at",
            "last_health_check_at",
            "last_error",
            "connected_at",
            "token_expires_at",
        ):
            base[field] = connection.get(field)
        return base

    async def health_check(self, shop_id: str, user_id: str) -> Dict[str, Any]:
        from app.services.meta_whatsapp_service import meta_whatsapp_service

        connection = self._existing_connection(shop_id)
        if not connection or connection.get("status") not in {
            "active",
            "reconnect_required",
        }:
            raise RuntimeError("NoActiveConnection")
        token = meta_whatsapp_service._resolve_access_token(connection)
        if not token:
            raise RuntimeError("CredentialUnavailable")
        try:
            health = await self._request(
                "GET",
                self._graph_url(str(connection["phone_number_id"])),
                token=token,
                params={"fields": "id,display_phone_number,verified_name,quality_rating"},
            )
        except Exception:
            supabase_client.table("whatsapp_connections").update(
                {"status": "reconnect_required", "last_error": "HealthCheckFailed"}
            ).eq("id", connection["id"]).execute()
            self._audit(
                shop_id,
                "reconnect_required",
                user_id,
                connection["id"],
                {"reason": "HealthCheckFailed"},
            )
            raise
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        supabase_client.table("whatsapp_connections").update(
            {
                "status": "active",
                "last_health_check_at": now,
                "last_error": None,
                "failure_count": 0,
                "display_phone_number": health.get("display_phone_number"),
                "verified_name": health.get("verified_name"),
            }
        ).eq("id", connection["id"]).execute()
        self._audit(shop_id, "health_checked", user_id, connection["id"])
        return {
            "healthy": True,
            "status": "active",
            "display_phone_number": health.get("display_phone_number"),
            "verified_name": health.get("verified_name"),
        }

    async def disconnect(self, shop_id: str, user_id: str) -> None:
        from app.services.meta_whatsapp_service import meta_whatsapp_service

        self._require_enabled(shop_id)
        connection = self._existing_connection(shop_id)
        if not connection:
            return
        token = meta_whatsapp_service._resolve_access_token(connection)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Stop tenant routing before making any external request.
        supabase_client.table("whatsapp_connections").update(
            {
                "status": "disconnected",
                "disconnected_at": now,
                "disconnected_by": user_id,
                "last_error": None,
            }
        ).eq("id", connection["id"]).eq("shop_id", shop_id).execute()

        other = (
            supabase_client.table("whatsapp_connections")
            .select("id")
            .eq("provider", "meta_cloud")
            .eq("waba_id", connection["waba_id"])
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if token and not other.data:
            try:
                await self._request(
                    "DELETE",
                    self._graph_url(f"{connection['waba_id']}/subscribed_apps"),
                    token=token,
                )
            except Exception as exc:
                logger.warning(
                    "Meta WABA unsubscribe failed connection_id=%s error_type=%s",
                    connection["id"],
                    type(exc).__name__,
                )
        supabase_client.table("whatsapp_connection_credentials").delete().eq(
            "connection_id", connection["id"]
        ).execute()
        supabase_client.table("whatsapp_connections").update(
            {"token_reference": None}
        ).eq("id", connection["id"]).execute()
        self._audit(
            shop_id, "connection_disconnected", user_id, connection["id"]
        )


meta_whatsapp_onboarding_service = MetaWhatsAppOnboardingService()
