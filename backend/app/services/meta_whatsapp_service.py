import datetime
import hashlib
import logging
import os
import re
import uuid
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

    _PLACEHOLDER_CUSTOMER_NAMES = {
        "",
        "unknown",
        "whatsapp customer",
        "meta whatsapp customer",
    }

    def _graph_url(self, path: str) -> str:
        version = settings.META_GRAPH_API_VERSION.strip("/") or "v25.0"
        return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"

    _TOKEN_REFERENCE_PATTERN = re.compile(
        r"^env:(META_WHATSAPP_ACCESS_TOKEN|META_WHATSAPP_TOKEN_[A-Z0-9_]+)$"
    )

    def _resolve_access_token(self, connection: Dict[str, Any]) -> Optional[str]:
        reference = str(connection.get("token_reference") or "").strip()
        if reference:
            match = self._TOKEN_REFERENCE_PATTERN.fullmatch(reference)
            if not match:
                logger.error("Meta connection has an invalid credential reference")
                return None
            return os.getenv(match.group(1))
        # Backward-compatible pilot token. New connections should store an
        # environment/secret-manager reference, never token plaintext.
        return settings.META_WHATSAPP_ACCESS_TOKEN or None

    def _auth_headers(self, connection: Dict[str, Any]) -> Dict[str, str]:
        token = self._resolve_access_token(connection)
        if not token:
            raise RuntimeError("Meta WhatsApp credential is unavailable")
        return {"Authorization": f"Bearer {token}"}

    def resolve_connection(
        self,
        phone_number_id: str,
        *,
        allow_default: Optional[bool] = None,
        raise_on_error: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if supabase_client:
            try:
                result = (
                    supabase_client.table("whatsapp_connections")
                    .select(
                        "id, shop_id, waba_id, phone_number_id, status, token_reference"
                    )
                    .eq("provider", "meta_cloud")
                    .eq("phone_number_id", phone_number_id)
                    .eq("status", "active")
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
            except Exception as exc:
                if raise_on_error:
                    raise RuntimeError("Meta connection lookup failed") from exc
                logger.warning(
                    "Meta WhatsApp connection lookup failed phone_number_id=%s error_type=%s",
                    phone_number_id,
                    type(exc).__name__,
                )

        fallback_enabled = (
            settings.META_WHATSAPP_ALLOW_DEFAULT_CONNECTION_FALLBACK
            if allow_default is None
            else allow_default
        )
        if (
            fallback_enabled
            and settings.META_WHATSAPP_DEFAULT_SHOP_ID
            and settings.META_WHATSAPP_PHONE_NUMBER_ID == phone_number_id
        ):
            return {
                "id": None,
                "shop_id": settings.META_WHATSAPP_DEFAULT_SHOP_ID,
                "waba_id": settings.META_WHATSAPP_WABA_ID,
                "phone_number_id": phone_number_id,
                "status": "active",
                "token_reference": "env:META_WHATSAPP_ACCESS_TOKEN",
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
            channel = existing.data[0]
            inbound_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            metadata = dict(channel.get("metadata") or {})
            metadata["last_inbound_at"] = inbound_at
            if profile_name:
                metadata["whatsapp_profile_name"] = profile_name

            customer = channel.get("customers") or {}
            has_confirmed_profile = bool(
                str(customer.get("name") or "").strip().lower()
                not in self._PLACEHOLDER_CUSTOMER_NAMES
                and str(
                    customer.get("default_address")
                    or customer.get("address")
                    or ""
                ).strip()
            )
            identity_verified = bool(
                metadata.get("identity_verified", has_confirmed_profile)
            )
            updates = {
                "metadata": {**metadata, "identity_verified": identity_verified}
            }
            if not identity_verified:
                current_state = str(channel.get("state") or "")
                updates.update(
                    {
                        "profile_completed": False,
                        "state": (
                            current_state
                            if current_state in {"awaiting_name", "awaiting_address"}
                            else "awaiting_name"
                        ),
                    }
                )
            supabase_client.table("customer_channels").update(updates).eq(
                "id", channel["id"]
            ).execute()
            channel["metadata"] = metadata
            channel.update(updates)
            return channel

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
                        # A WhatsApp display name is not verified order identity.
                        "name": "WhatsApp Customer",
                        "phone": phone,
                    }
                )
                .execute()
            )
            if created.data:
                customer = created.data[0]
        if not customer:
            return None

        has_confirmed_profile = bool(
            str(customer.get("name") or "").strip().lower()
            not in self._PLACEHOLDER_CUSTOMER_NAMES
            and str(
                customer.get("default_address") or customer.get("address") or ""
            ).strip()
        )
        channel_payload = {
            "shop_id": shop_id,
            "customer_id": customer["id"],
            "channel": "meta_whatsapp",
            "channel_user_id": wa_id,
            "channel_chat_id": wa_id,
            "phone": phone,
            "display_name": customer.get("name") if has_confirmed_profile else None,
            "state": "ready" if has_confirmed_profile else "awaiting_name",
            "profile_completed": has_confirmed_profile,
            "metadata": {
                "last_inbound_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
                "whatsapp_profile_name": profile_name,
                "identity_verified": has_confirmed_profile,
            },
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

    @staticmethod
    def _looks_like_order(text: str) -> bool:
        classification = IntentRouter.classify_intent_deterministically(text)
        return bool(
            classification
            and classification.intent.value == "new_order"
            and classification.confidence >= 0.60
        )

    def _has_active_order_draft(
        self, shop_id: str, customer_id: str
    ) -> bool:
        if not supabase_client:
            return False
        try:
            result = (
                supabase_client.table("customer_conversations")
                .select("id")
                .eq("shop_id", shop_id)
                .eq("customer_id", customer_id)
                .eq("channel", "meta_whatsapp")
                .in_("state", ["collecting_details", "awaiting_confirmation"])
                .limit(1)
                .execute()
            )
            return bool(result.data)
        except Exception as exc:
            logger.warning(
                "Meta order draft lookup failed customer_id=%s error_type=%s",
                customer_id,
                type(exc).__name__,
            )
            return False

    @staticmethod
    def _extract_name_reply(text: str) -> Optional[str]:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        match = re.search(
            r"^(?:my name is|mera naam|naam)\s+(.+)$",
            cleaned,
            flags=re.IGNORECASE,
        )
        candidate = (match.group(1) if match else cleaned).strip(" .,-")
        if (
            not candidate
            or len(candidate) > 80
            or any(char.isdigit() for char in candidate)
            or re.fullmatch(
                r"(?:hi|hello|hey|namaste|namaskar|नमस्ते|नमस्कार)[!. ]*",
                candidate,
                flags=re.IGNORECASE,
            )
        ):
            return None
        return candidate

    def _handle_profile_message(
        self,
        channel: Dict[str, Any],
        customer: Dict[str, Any],
        text: str,
    ) -> Optional[str]:
        state = str(channel.get("state") or "awaiting_name")
        if state in {"awaiting_name", "updating_name"}:
            name = self._extract_name_reply(text)
            if not name:
                return "Please apna sahi naam batayein."
            supabase_client.table("customers").update({"name": name}).eq(
                "id", customer["id"]
            ).eq("shop_id", channel["shop_id"]).execute()
            if state == "updating_name":
                supabase_client.table("customer_channels").update(
                    {
                        "display_name": name,
                        "state": "ready",
                        "profile_completed": True,
                    }
                ).eq("id", channel["id"]).eq(
                    "shop_id", channel["shop_id"]
                ).execute()
                return f"Name updated: {name}"
            supabase_client.table("customer_channels").update(
                {"display_name": name, "state": "awaiting_address"}
            ).eq("id", channel["id"]).eq(
                "shop_id", channel["shop_id"]
            ).execute()
            return "Thanks! Apna delivery address batayein."

        if state in {"awaiting_address", "updating_address"}:
            address = re.sub(
                r"^(?:address|delivery address)\s*(?:is|hai|:)?\s*",
                "",
                str(text or "").strip(),
                flags=re.IGNORECASE,
            ).strip()
            if len(address) < 5:
                return "Please poora delivery address bhejein."
            supabase_client.table("customers").update(
                {"address": address, "default_address": address}
            ).eq("id", customer["id"]).eq(
                "shop_id", channel["shop_id"]
            ).execute()
            metadata = dict(channel.get("metadata") or {})
            metadata["identity_verified"] = True
            supabase_client.table("customer_channels").update(
                {
                    "state": "ready",
                    "profile_completed": True,
                    "metadata": metadata,
                }
            ).eq("id", channel["id"]).eq(
                "shop_id", channel["shop_id"]
            ).execute()
            if state == "updating_address":
                return f"Delivery address updated: {address}"
            return "Profile saved. Ab apna order text ya voice note mein bhejein."

        return None

    def _handle_profile_command(
        self,
        channel: Dict[str, Any],
        customer: Dict[str, Any],
        text: str,
        *,
        has_active_draft: bool,
    ) -> Optional[str]:
        command = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if command in {"/", "menu", "/menu", "help", "/help"}:
            return (
                "PhoneERP menu:\n"
                "• Order bhejne ke liye items aur quantity likhein\n"
                "• Order status ke liye: track my order\n"
                "• Profile dekhne ke liye: profile\n"
                "• Naam badalne ke liye: edit name\n"
                "• Address badalne ke liye: edit address"
            )

        profile_commands = {
            "profile",
            "/profile",
            "my profile",
            "mera profile",
            "profile dikhao",
        }
        if command in profile_commands:
            name = str(customer.get("name") or "Not saved").strip()
            address = str(
                customer.get("default_address")
                or customer.get("address")
                or "Not saved"
            ).strip()
            return (
                f"Your PhoneERP profile:\nName: {name}\n"
                f"Delivery address: {address}\n"
                "Update ke liye 'edit name' ya 'edit address' bhejein."
            )

        name_commands = {
            "edit name",
            "/name",
            "change name",
            "update name",
            "naam badlo",
            "naam change",
        }
        address_commands = {
            "edit address",
            "/address",
            "change address",
            "update address",
            "address badlo",
            "address change",
        }
        if command not in name_commands | address_commands:
            return None
        if has_active_draft:
            return (
                "Pehle current order details complete karein. "
                "Uske baad profile update kar sakte hain."
            )

        next_state = (
            "updating_name" if command in name_commands else "updating_address"
        )
        supabase_client.table("customer_channels").update(
            {"state": next_state}
        ).eq("id", channel["id"]).eq("shop_id", channel["shop_id"]).execute()
        return (
            "Apna naya naam batayein."
            if next_state == "updating_name"
            else "Apna naya poora delivery address batayein."
        )

    async def send_text(
        self, to_wa_id: str, body: str, phone_number_id: Optional[str] = None
    ) -> Dict[str, Any]:
        sender_id = phone_number_id or settings.META_WHATSAPP_PHONE_NUMBER_ID
        connection = self.resolve_connection(sender_id) if sender_id else None
        if not sender_id or not connection:
            return {"sent": False, "error": "Meta WhatsApp is not configured"}

        outbound_id = self._record_outbound_pending(connection, to_wa_id)
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
                    headers={
                        **self._auth_headers(connection),
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            message_id = (data.get("messages") or [{}])[0].get("id")
            if not message_id:
                raise RuntimeError("Meta send response did not include a message id")
            self._record_outbound_result(
                outbound_id, sent=True, provider_message_id=message_id
            )
            return {"sent": True, "message_id": message_id}
        except Exception as exc:
            self._record_outbound_result(outbound_id, sent=False)
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
        connection = self.resolve_connection(sender_id) if sender_id else None
        if not sender_id or not connection:
            return {"sent": False, "error": "Meta WhatsApp is not configured"}
        outbound_id = self._record_outbound_pending(connection, to_wa_id)
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
                    headers={
                        **self._auth_headers(connection),
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            message_id = (data.get("messages") or [{}])[0].get("id")
            if not message_id:
                raise RuntimeError("Meta send response did not include a message id")
            self._record_outbound_result(
                outbound_id, sent=True, provider_message_id=message_id
            )
            return {"sent": True, "message_id": message_id}
        except Exception as exc:
            self._record_outbound_result(outbound_id, sent=False)
            logger.error(
                "Meta WhatsApp send failed phone_number_id=%s error_type=%s",
                sender_id,
                type(exc).__name__,
            )
            return {"sent": False, "error": "Meta API request failed"}

    def _record_outbound_pending(
        self, connection: Dict[str, Any], recipient_wa_id: str
    ) -> Optional[str]:
        if not supabase_client or not connection.get("id"):
            return None
        outbound_id = str(uuid.uuid4())
        try:
            supabase_client.table("whatsapp_outbound_messages").insert(
                {
                    "id": outbound_id,
                    "provider": "meta_cloud",
                    "connection_id": connection["id"],
                    "shop_id": connection["shop_id"],
                    "phone_number_id": connection["phone_number_id"],
                    "recipient_hash": hashlib.sha256(
                        recipient_wa_id.encode("utf-8")
                    ).hexdigest(),
                    "message_type": "text",
                    "delivery_status": "pending",
                }
            ).execute()
            return outbound_id
        except Exception as exc:
            logger.warning(
                "Meta outbound status insert failed error_type=%s",
                type(exc).__name__,
            )
            return None

    def _record_outbound_result(
        self,
        outbound_id: Optional[str],
        *,
        sent: bool,
        provider_message_id: Optional[str] = None,
    ) -> None:
        if not supabase_client or not outbound_id:
            return
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        updates: Dict[str, Any] = {
            "delivery_status": "accepted" if sent else "failed",
            "sent_at": now if sent else None,
            "failed_at": None if sent else now,
        }
        if provider_message_id:
            updates["provider_message_id"] = provider_message_id
        try:
            supabase_client.table("whatsapp_outbound_messages").update(updates).eq(
                "id", outbound_id
            ).execute()
        except Exception as exc:
            logger.warning(
                "Meta outbound status update failed error_type=%s",
                type(exc).__name__,
            )

    @staticmethod
    def _provider_timestamp(value: Any) -> str:
        try:
            timestamp = datetime.datetime.fromtimestamp(
                int(value), tz=datetime.timezone.utc
            )
        except (TypeError, ValueError, OSError):
            timestamp = datetime.datetime.now(datetime.timezone.utc)
        return timestamp.isoformat()

    def process_status(
        self, connection: Dict[str, Any], status_payload: Dict[str, Any]
    ) -> None:
        if not supabase_client:
            raise RuntimeError("Message status database is unavailable")
        provider_message_id = str(status_payload.get("id") or "")
        provider_status = str(status_payload.get("status") or "").lower()
        if not provider_message_id or provider_status not in {
            "sent",
            "delivered",
            "read",
            "failed",
        }:
            return

        occurred_at = self._provider_timestamp(status_payload.get("timestamp"))
        updates: Dict[str, Any] = {"delivery_status": provider_status}
        updates[f"{provider_status}_at"] = occurred_at
        errors = status_payload.get("errors") or []
        if provider_status == "failed" and errors:
            updates["provider_error_code"] = str(errors[0].get("code") or "")[:64]

        existing = (
            supabase_client.table("whatsapp_outbound_messages")
            .select("id")
            .eq("provider", "meta_cloud")
            .eq("provider_message_id", provider_message_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            supabase_client.table("whatsapp_outbound_messages").update(updates).eq(
                "id", existing.data[0]["id"]
            ).execute()
            return

        # A status can arrive for a message sent before this ledger was deployed.
        supabase_client.table("whatsapp_outbound_messages").insert(
            {
                "provider": "meta_cloud",
                "connection_id": connection.get("id"),
                "shop_id": connection["shop_id"],
                "phone_number_id": connection["phone_number_id"],
                "provider_message_id": provider_message_id,
                "recipient_hash": "unknown",
                "message_type": "text",
                **updates,
            }
        ).execute()

    async def _transcribe_audio(
        self, media_id: str, connection: Dict[str, Any]
    ) -> Optional[str]:
        allowed_mime_types = {
            "audio/aac",
            "audio/amr",
            "audio/mpeg",
            "audio/mp4",
            "audio/ogg",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            metadata_response = await client.get(
                self._graph_url(media_id), headers=self._auth_headers(connection)
            )
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
            media_url = metadata.get("url")
            if not media_url:
                return None
            mime_type = str(metadata.get("mime_type") or "").split(";")[0].lower()
            if mime_type not in allowed_mime_types:
                raise ValueError("Unsupported WhatsApp audio MIME type")
            try:
                declared_size = int(metadata.get("file_size") or 0)
            except (TypeError, ValueError):
                declared_size = 0
            if declared_size > settings.META_WHATSAPP_MAX_MEDIA_BYTES:
                raise ValueError("WhatsApp audio exceeds configured size limit")

            content = bytearray()
            async with client.stream(
                "GET", media_url, headers=self._auth_headers(connection)
            ) as media_response:
                media_response.raise_for_status()
                content_length = int(media_response.headers.get("content-length") or 0)
                if content_length > settings.META_WHATSAPP_MAX_MEDIA_BYTES:
                    raise ValueError("WhatsApp audio exceeds configured size limit")
                async for chunk in media_response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > settings.META_WHATSAPP_MAX_MEDIA_BYTES:
                        raise ValueError("WhatsApp audio exceeds configured size limit")

        extension = "ogg" if "ogg" in mime_type else "mp4" if "mp4" in mime_type else "bin"
        return await GeminiService.transcribe_audio_file(
            bytes(content), f"meta-voice.{extension}", mime_type
        )

    async def process_message(
        self,
        phone_number_id: str,
        message: Dict[str, Any],
        contact: Optional[Dict[str, Any]] = None,
        *,
        connection: Optional[Dict[str, Any]] = None,
    ) -> bool:
        message_id = str(message.get("id") or "")
        wa_id = str(message.get("from") or "")
        if not message_id or not wa_id:
            raise ValueError("Malformed Meta WhatsApp message")

        connection = connection or self.resolve_connection(phone_number_id)
        if not connection:
            raise RuntimeError("No active PhoneERP shop mapping")

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
                raw_text = (
                    await self._transcribe_audio(media_id, connection)
                    if media_id
                    else None
                )
                normalized_type = "voice"
            else:
                await self.send_text(
                    wa_id,
                    "Please send your order as text or a WhatsApp voice note.",
                    phone_number_id,
                )
                return True

            if not raw_text:
                await self.send_text(
                    wa_id,
                    "I could not read that message. Please send it again as text.",
                    phone_number_id,
                )
                return True

            has_active_draft = self._has_active_order_draft(
                connection["shop_id"], customer_id
            )
            if normalized_type == "text":
                profile_command_reply = self._handle_profile_command(
                    channel,
                    customer,
                    raw_text,
                    has_active_draft=has_active_draft,
                )
                if profile_command_reply:
                    await self.send_text(
                        wa_id, profile_command_reply, phone_number_id
                    )
                    return True

            channel_state = str(channel.get("state") or "")
            if (
                normalized_type == "text"
                and (
                    channel.get("profile_completed") is False
                    or channel_state in {"updating_name", "updating_address"}
                )
                and not has_active_draft
                and not self._looks_like_order(raw_text)
            ):
                profile_reply = self._handle_profile_message(
                    channel, customer, raw_text
                )
                if profile_reply:
                    await self.send_text(wa_id, profile_reply, phone_number_id)
                    return True

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
                    "customer_profile_completed": bool(
                        channel.get("profile_completed")
                    ),
                    "input_type": normalized_type,
                },
            )
            result = await IntentRouter.process_inbound_message(inbound)
            reply = result.get("reply_message")
            if reply:
                await self.send_text(wa_id, reply, phone_number_id)
            return True
        except Exception as exc:
            logger.exception(
                "Meta WhatsApp message processing failed message_id=%s error_type=%s",
                message_id,
                type(exc).__name__,
            )
            raise


meta_whatsapp_service = MetaWhatsAppService()
