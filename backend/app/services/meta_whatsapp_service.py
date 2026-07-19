import logging
from typing import Any, Dict, Optional

import httpx

from app.config.settings import settings
from app.schemas.inbound import NormalizedInboundMessage
from app.services.gemini import GeminiService
from app.services.intent_router import IntentRouter
from app.services.supabase import supabase_client
from app.utils.phone import normalize_phone


logger = logging.getLogger(__name__)


class MetaWhatsAppService:
    """Adapter from Meta Cloud API payloads to PhoneERP's inbound pipeline."""

    def _graph_url(self, path: str) -> str:
        version = settings.META_GRAPH_API_VERSION.strip("/") or "v25.0"
        return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {settings.META_WHATSAPP_ACCESS_TOKEN}"}

    def resolve_connection(self, phone_number_id: str) -> Optional[Dict[str, Any]]:
        if supabase_client:
            try:
                result = (
                    supabase_client.table("whatsapp_connections")
                    .select("id, shop_id, waba_id, phone_number_id, status")
                    .eq("provider", "meta_cloud")
                    .eq("phone_number_id", phone_number_id)
                    .eq("status", "active")
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
            except Exception as exc:
                logger.warning(
                    "Meta WhatsApp connection lookup failed phone_number_id=%s error_type=%s",
                    phone_number_id,
                    type(exc).__name__,
                )

        if (
            settings.META_WHATSAPP_DEFAULT_SHOP_ID
            and settings.META_WHATSAPP_PHONE_NUMBER_ID == phone_number_id
        ):
            return {
                "shop_id": settings.META_WHATSAPP_DEFAULT_SHOP_ID,
                "waba_id": settings.META_WHATSAPP_WABA_ID,
                "phone_number_id": phone_number_id,
                "status": "active",
            }
        return None

    def get_or_create_customer(
        self, shop_id: str, wa_id: str, profile_name: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        if not supabase_client:
            return None

        channel_query = (
            supabase_client.table("customer_channels")
            .select("*, customers(*)")
            .eq("shop_id", shop_id)
            .eq("channel", "meta_whatsapp")
            .eq("channel_user_id", wa_id)
        )
        existing = channel_query.execute()
        if existing.data:
            return existing.data[0]

        phone = normalize_phone(wa_id)
        customer = None
        customer_result = (
            supabase_client.table("customers")
            .select("*")
            .eq("shop_id", shop_id)
            .eq("phone", phone)
            .limit(1)
            .execute()
        )
        if customer_result.data:
            customer = customer_result.data[0]
        else:
            created = (
                supabase_client.table("customers")
                .insert(
                    {
                        "shop_id": shop_id,
                        "name": profile_name or "WhatsApp Customer",
                        "phone": phone,
                    }
                )
                .execute()
            )
            if created.data:
                customer = created.data[0]
        if not customer:
            return None

        channel_payload = {
            "shop_id": shop_id,
            "customer_id": customer["id"],
            "channel": "meta_whatsapp",
            "channel_user_id": wa_id,
            "channel_chat_id": wa_id,
            "phone": phone,
            "state": "ready",
            "profile_completed": True,
        }
        try:
            created_channel = (
                supabase_client.table("customer_channels")
                .insert(channel_payload)
                .execute()
            )
            if created_channel.data:
                data = created_channel.data[0]
                data["customers"] = customer
                return data
        except Exception:
            # A retried webhook may race another request against the unique key.
            existing = channel_query.execute()
            if existing.data:
                return existing.data[0]
            raise
        return None

    async def send_text(
        self, to_wa_id: str, body: str, phone_number_id: Optional[str] = None
    ) -> Dict[str, Any]:
        sender_id = phone_number_id or settings.META_WHATSAPP_PHONE_NUMBER_ID
        if not settings.META_WHATSAPP_ACCESS_TOKEN or not sender_id:
            return {"sent": False, "error": "Meta WhatsApp is not configured"}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_wa_id,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    self._graph_url(f"{sender_id}/messages"),
                    headers={**self._auth_headers(), "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            message_id = (data.get("messages") or [{}])[0].get("id")
            return {"sent": True, "message_id": message_id}
        except httpx.HTTPError as exc:
            logger.error(
                "Meta WhatsApp send failed phone_number_id=%s error_type=%s",
                sender_id,
                type(exc).__name__,
            )
            return {"sent": False, "error": "Meta API request failed"}

    def send_text_sync(
        self, to_wa_id: str, body: str, phone_number_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous sender for lifecycle hooks that are currently synchronous."""
        sender_id = phone_number_id or settings.META_WHATSAPP_PHONE_NUMBER_ID
        if not settings.META_WHATSAPP_ACCESS_TOKEN or not sender_id:
            return {"sent": False, "error": "Meta WhatsApp is not configured"}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_wa_id,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
        try:
            with httpx.Client(timeout=15) as client:
                response = client.post(
                    self._graph_url(f"{sender_id}/messages"),
                    headers={**self._auth_headers(), "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            message_id = (data.get("messages") or [{}])[0].get("id")
            return {"sent": True, "message_id": message_id}
        except httpx.HTTPError as exc:
            logger.error(
                "Meta WhatsApp send failed phone_number_id=%s error_type=%s",
                sender_id,
                type(exc).__name__,
            )
            return {"sent": False, "error": "Meta API request failed"}

    async def _transcribe_audio(self, media_id: str) -> Optional[str]:
        async with httpx.AsyncClient(timeout=30) as client:
            metadata_response = await client.get(
                self._graph_url(media_id), headers=self._auth_headers()
            )
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
            media_url = metadata.get("url")
            if not media_url:
                return None
            media_response = await client.get(media_url, headers=self._auth_headers())
            media_response.raise_for_status()

        mime_type = str(metadata.get("mime_type") or "audio/ogg").split(";")[0]
        extension = "ogg" if "ogg" in mime_type else "mp4" if "mp4" in mime_type else "bin"
        return await GeminiService.transcribe_audio_file(
            media_response.content, f"meta-voice.{extension}", mime_type
        )

    async def process_message(
        self,
        phone_number_id: str,
        message: Dict[str, Any],
        contact: Optional[Dict[str, Any]] = None,
    ) -> None:
        message_id = str(message.get("id") or "")
        wa_id = str(message.get("from") or "")
        if not message_id or not wa_id:
            logger.warning("Ignoring malformed Meta WhatsApp message")
            return

        connection = self.resolve_connection(phone_number_id)
        if not connection:
            logger.error(
                "No active PhoneERP shop mapping for Meta phone_number_id=%s",
                phone_number_id,
            )
            return

        profile_name = ((contact or {}).get("profile") or {}).get("name")
        try:
            channel = self.get_or_create_customer(
                connection["shop_id"], wa_id, profile_name
            )
            if not channel:
                raise RuntimeError("Unable to resolve WhatsApp customer")
            customer = channel.get("customers") or {}
            customer_id = customer.get("id") or channel.get("customer_id")
            if not customer_id:
                raise RuntimeError("WhatsApp channel has no customer")

            message_type = message.get("type")
            if message_type == "text":
                raw_text = ((message.get("text") or {}).get("body") or "").strip()
                normalized_type = "text"
            elif message_type == "audio":
                media_id = (message.get("audio") or {}).get("id")
                raw_text = await self._transcribe_audio(media_id) if media_id else None
                normalized_type = "voice"
            else:
                await self.send_text(
                    wa_id,
                    "Please send your order as text or a WhatsApp voice note.",
                    phone_number_id,
                )
                return

            if not raw_text:
                await self.send_text(
                    wa_id,
                    "I could not read that message. Please send it again as text.",
                    phone_number_id,
                )
                return

            inbound = NormalizedInboundMessage(
                shop_id=connection["shop_id"],
                customer_id=customer_id,
                channel="meta_whatsapp",
                provider_message_id=message_id,
                message_type=normalized_type,
                raw_text=raw_text,
                metadata={
                    "source": "meta_whatsapp",
                    "input_channel": "meta_whatsapp",
                    "meta_phone_number_id": phone_number_id,
                    "meta_waba_id": connection.get("waba_id"),
                    "whatsapp_wa_id": wa_id,
                    "profile_name": profile_name,
                    "input_type": normalized_type,
                },
            )
            result = await IntentRouter.process_inbound_message(inbound)
            reply = result.get("reply_message")
            if reply:
                await self.send_text(wa_id, reply, phone_number_id)
        except Exception as exc:
            logger.exception(
                "Meta WhatsApp message processing failed message_id=%s error_type=%s",
                message_id,
                type(exc).__name__,
            )
            await self.send_text(
                wa_id,
                "Sorry, I could not process that message. Please try again.",
                phone_number_id,
            )


meta_whatsapp_service = MetaWhatsAppService()
