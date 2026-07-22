import asyncio
import datetime
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.config.settings import settings
from app.services.supabase import supabase_client


logger = logging.getLogger(__name__)


class MetaWhatsAppEventService:
    """Durable inbox and processor for verified Meta webhook events."""

    @staticmethod
    def _utc_now() -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    @staticmethod
    def _status_event_id(status_payload: Dict[str, Any]) -> str:
        message_id = str(status_payload.get("id") or "")
        status_name = str(status_payload.get("status") or "unknown")
        timestamp = str(status_payload.get("timestamp") or "")
        if message_id:
            return f"{message_id}:{status_name}:{timestamp}"
        canonical = json.dumps(status_payload, sort_keys=True, separators=(",", ":"))
        return "status:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_duplicate_error(exc: Exception) -> bool:
        code = str(getattr(exc, "code", ""))
        message = str(exc).lower()
        return code == "23505" or "duplicate key" in message

    def persist_webhook_payload(self, payload: Dict[str, Any]) -> List[str]:
        if not supabase_client:
            raise RuntimeError("Meta webhook inbox database is unavailable")

        # Imported lazily to avoid a module cycle while keeping connection
        # resolution centralized in the Meta adapter.
        from app.services.meta_whatsapp_service import meta_whatsapp_service

        persisted_ids: List[str] = []
        for entry in payload.get("entry") or []:
            entry_waba_id = str(entry.get("id") or "")
            for change in entry.get("changes") or []:
                if change.get("field") != "messages":
                    continue
                value = change.get("value") or {}
                metadata = value.get("metadata") or {}
                phone_number_id = str(metadata.get("phone_number_id") or "")
                if not phone_number_id:
                    logger.warning("Meta webhook event has no phone_number_id")
                    continue

                connection = meta_whatsapp_service.resolve_connection(
                    phone_number_id, allow_default=False, raise_on_error=True
                )
                contacts = {
                    str(contact.get("wa_id")): contact
                    for contact in value.get("contacts") or []
                    if contact.get("wa_id")
                }

                for message in value.get("messages") or []:
                    provider_event_id = str(message.get("id") or "")
                    if not provider_event_id:
                        logger.warning("Ignoring Meta message without provider id")
                        continue
                    event_payload = {
                        "message": message,
                        "contact": contacts.get(str(message.get("from"))),
                    }
                    event_id = self._insert_event(
                        event_kind="message",
                        provider_event_id=provider_event_id,
                        phone_number_id=phone_number_id,
                        waba_id=entry_waba_id or (connection or {}).get("waba_id"),
                        connection=connection,
                        payload=event_payload,
                    )
                    if event_id:
                        persisted_ids.append(event_id)

                for status_payload in value.get("statuses") or []:
                    event_id = self._insert_event(
                        event_kind="status",
                        provider_event_id=self._status_event_id(status_payload),
                        phone_number_id=phone_number_id,
                        waba_id=entry_waba_id or (connection or {}).get("waba_id"),
                        connection=connection,
                        payload={"status": status_payload},
                    )
                    if event_id:
                        persisted_ids.append(event_id)

                if connection:
                    self._record_connection_success(connection["id"])

        return persisted_ids

    def _insert_event(
        self,
        *,
        event_kind: str,
        provider_event_id: str,
        phone_number_id: str,
        waba_id: Optional[str],
        connection: Optional[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> Optional[str]:
        processing_status = "pending" if connection else "unroutable"
        row = {
            "provider": "meta_cloud",
            "event_kind": event_kind,
            "provider_event_id": provider_event_id,
            "connection_id": (connection or {}).get("id"),
            "shop_id": (connection or {}).get("shop_id"),
            "waba_id": waba_id or None,
            "phone_number_id": phone_number_id,
            "payload": payload,
            "processing_status": processing_status,
            "last_error": None if connection else "ConnectionNotMapped",
        }
        try:
            result = (
                supabase_client.table("whatsapp_webhook_events")
                .insert(row)
                .execute()
            )
            if not result.data:
                raise RuntimeError("Meta webhook inbox insert returned no row")
            if not connection:
                logger.error(
                    "Meta webhook event is unroutable phone_number_id=%s",
                    phone_number_id,
                )
            return result.data[0]["id"]
        except Exception as exc:
            if self._is_duplicate_error(exc):
                return None
            raise

    def claim_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        if not supabase_client:
            return None
        result = (
            supabase_client.table("whatsapp_webhook_events")
            .select("*")
            .eq("id", event_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        event = result.data[0]
        if event.get("processing_status") not in ("pending", "retry"):
            return None
        attempts = int(event.get("attempts") or 0)
        claimed = (
            supabase_client.table("whatsapp_webhook_events")
            .update(
                {
                    "processing_status": "processing",
                    "attempts": attempts + 1,
                    "locked_at": self._utc_now(),
                    "last_error": None,
                }
            )
            .eq("id", event_id)
            .eq("processing_status", event["processing_status"])
            .execute()
        )
        return claimed.data[0] if claimed.data else None

    def claim_batch(self, limit: int) -> List[Dict[str, Any]]:
        if not supabase_client:
            raise RuntimeError("Meta webhook worker database is unavailable")
        result = supabase_client.rpc(
            "claim_meta_whatsapp_events", {"p_limit": max(1, min(limit, 50))}
        ).execute()
        return result.data or []

    async def process_event(self, event_id: str) -> bool:
        event = self.claim_event(event_id)
        if not event:
            return False
        return await self.process_claimed_event(event)

    async def process_claimed_event(self, event: Dict[str, Any]) -> bool:
        event_id = event["id"]
        connection_id = event.get("connection_id")
        try:
            from app.services.meta_whatsapp_service import meta_whatsapp_service

            connection = meta_whatsapp_service.resolve_connection(
                str(event.get("phone_number_id") or ""),
                allow_default=False,
                raise_on_error=True,
            )
            if not connection or connection.get("id") != connection_id:
                raise RuntimeError("Meta WhatsApp connection is inactive or changed")

            payload = event.get("payload") or {}
            if event.get("event_kind") == "message":
                await meta_whatsapp_service.process_message(
                    event["phone_number_id"],
                    payload.get("message") or {},
                    payload.get("contact"),
                    connection=connection,
                )
            elif event.get("event_kind") == "status":
                meta_whatsapp_service.process_status(
                    connection, payload.get("status") or {}
                )
            else:
                raise RuntimeError("Unsupported Meta webhook event kind")

            self._mark_completed(event_id)
            self._record_connection_success(connection_id)
            return True
        except Exception as exc:
            dead_lettered = self._mark_failed(event, exc)
            if connection_id:
                self._record_connection_failure(connection_id, exc)
            if dead_lettered and event.get("event_kind") == "message":
                await self._send_terminal_failure_reply(event)
            logger.error(
                "Meta webhook event processing failed event_id=%s error_type=%s",
                event_id,
                type(exc).__name__,
            )
            return False

    def _mark_completed(self, event_id: str) -> None:
        supabase_client.table("whatsapp_webhook_events").update(
            {
                "processing_status": "completed",
                "processed_at": self._utc_now(),
                "locked_at": None,
                "last_error": None,
            }
        ).eq("id", event_id).eq("processing_status", "processing").execute()

    def _mark_failed(self, event: Dict[str, Any], exc: Exception) -> bool:
        attempts = int(event.get("attempts") or 1)
        max_attempts = int(event.get("max_attempts") or 6)
        dead_letter = attempts >= max_attempts
        retry_seconds = min(
            settings.META_WHATSAPP_RETRY_BASE_SECONDS * (2 ** max(attempts - 1, 0)),
            15 * 60,
        )
        available_at = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(seconds=retry_seconds)
        ).isoformat()
        supabase_client.table("whatsapp_webhook_events").update(
            {
                "processing_status": "dead_letter" if dead_letter else "retry",
                "available_at": available_at,
                "locked_at": None,
                "last_error": type(exc).__name__[:255],
            }
        ).eq("id", event["id"]).eq("processing_status", "processing").execute()
        return dead_letter

    async def _send_terminal_failure_reply(self, event: Dict[str, Any]) -> None:
        message = (event.get("payload") or {}).get("message") or {}
        recipient = str(message.get("from") or "")
        phone_number_id = str(event.get("phone_number_id") or "")
        if not recipient or not phone_number_id:
            return
        try:
            from app.services.meta_whatsapp_service import meta_whatsapp_service

            await meta_whatsapp_service.send_text(
                recipient,
                "Sorry, I could not process that message. Please try again.",
                phone_number_id,
            )
        except Exception as reply_exc:
            logger.error(
                "Meta terminal failure reply failed event_id=%s error_type=%s",
                event.get("id"),
                type(reply_exc).__name__,
            )

    def _record_connection_success(self, connection_id: str) -> None:
        try:
            supabase_client.table("whatsapp_connections").update(
                {
                    "last_webhook_at": self._utc_now(),
                    "last_health_check_at": self._utc_now(),
                    "last_error": None,
                    "failure_count": 0,
                }
            ).eq("id", connection_id).execute()
        except Exception as exc:
            logger.warning(
                "Meta connection health update failed error_type=%s",
                type(exc).__name__,
            )

    def _record_connection_failure(self, connection_id: str, exc: Exception) -> None:
        try:
            result = (
                supabase_client.table("whatsapp_connections")
                .select("failure_count")
                .eq("id", connection_id)
                .limit(1)
                .execute()
            )
            current = int((result.data or [{}])[0].get("failure_count") or 0)
            supabase_client.table("whatsapp_connections").update(
                {
                    "last_health_check_at": self._utc_now(),
                    "last_error": type(exc).__name__[:255],
                    "failure_count": current + 1,
                }
            ).eq("id", connection_id).execute()
        except Exception as health_exc:
            logger.warning(
                "Meta connection failure record failed error_type=%s",
                type(health_exc).__name__,
            )

    async def run_worker_forever(self) -> None:
        logger.info("Meta WhatsApp durable worker started")
        last_cleanup = 0.0
        while True:
            try:
                if time.monotonic() - last_cleanup >= 60 * 60:
                    self.purge_expired_events()
                    last_cleanup = time.monotonic()
                events = self.claim_batch(settings.META_WHATSAPP_WORKER_BATCH_SIZE)
                if not events:
                    await asyncio.sleep(settings.META_WHATSAPP_WORKER_POLL_SECONDS)
                    continue
                for event in events:
                    await self.process_claimed_event(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "Meta WhatsApp worker loop failed error_type=%s",
                    type(exc).__name__,
                )
                await asyncio.sleep(max(settings.META_WHATSAPP_WORKER_POLL_SECONDS, 1))

    def purge_expired_events(self) -> None:
        if not supabase_client:
            return
        try:
            supabase_client.table("whatsapp_webhook_events").delete().lt(
                "retention_expires_at", self._utc_now()
            ).execute()
        except Exception as exc:
            logger.warning(
                "Meta webhook retention cleanup failed error_type=%s",
                type(exc).__name__,
            )


meta_whatsapp_event_service = MetaWhatsAppEventService()
