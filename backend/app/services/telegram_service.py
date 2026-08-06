import logging
import requests
import re
from contextvars import ContextVar
from typing import Optional, Dict, Any
from app.config.settings import settings
from app.services.supabase import supabase_client

logger = logging.getLogger(__name__)

def normalize_phone(phone: str) -> Optional[str]:
    if not phone or phone.lower().strip() == "skip":
        return None
    cleaned = re.sub(r'[\s-]', '', phone)
    if re.match(r'^\+91\d{10}$', cleaned):
        return cleaned
    if re.match(r'^91\d{10}$', cleaned):
        return '+' + cleaned
    if re.match(r'^\d{10}$', cleaned):
        return '+91' + cleaned
    return None

class TelegramService:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._request_bot_token: ContextVar[Optional[str]] = ContextVar(
            "telegram_request_bot_token", default=None
        )

    def _current_bot_token(self) -> str:
        return self._request_bot_token.get() or settings.TELEGRAM_BOT_TOKEN
    
    def send_message(self, chat_id: str, text: str) -> bool:
        bot_token = self._current_bot_token()
        if not bot_token:
            logger.warning("No Telegram bot credential is available. Cannot send message.")
            return False
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            safe_error = str(e).replace(bot_token, "***TOKEN***")
            logger.error("Failed to send Telegram message: %s", safe_error)
            return False

    def send_message_for_shop(self, shop_id: str, chat_id: str, text: str) -> None:
        """Send through the bot connected to the order's shop."""
        bot_token: Optional[str] = None
        try:
            from app.services.telegram_connection_service import (
                telegram_connection_service,
            )

            connection = telegram_connection_service.resolve_shop_connection(shop_id)
            if connection:
                bot_token = telegram_connection_service.resolve_token(connection)
            elif shop_id == settings.TELEGRAM_DEFAULT_SHOP_ID:
                bot_token = settings.TELEGRAM_BOT_TOKEN or None
        except Exception as exc:
            logger.error(
                "Telegram outbound routing failed shop_id=%s error_type=%s",
                shop_id,
                type(exc).__name__,
            )
        if not bot_token:
            raise RuntimeError("NoActiveTelegramConnection")
        token_context = self._request_bot_token.set(bot_token)
        try:
            if not self.send_message(chat_id, text):
                raise RuntimeError("TelegramMessageSendFailed")
        finally:
            self._request_bot_token.reset(token_context)

    def _resolve_shop_and_owner(self) -> tuple[Optional[str], Optional[str]]:
        shop_id = settings.TELEGRAM_DEFAULT_SHOP_ID
        owner_id = settings.TELEGRAM_DEFAULT_OWNER_ID
        
        if not shop_id and settings.TELEGRAM_DEFAULT_OWNER_EMAIL and supabase_client:
            # Try to lookup owner by email in public.shops
            try:
                # We can't query auth.users directly without service role, so we check if there's a shop linked to this email? 
                # Actually, our shops table has owner_id, but not owner_email. 
                pass
            except Exception:
                pass
                
        return shop_id, owner_id

    def _resolve_connection_context(
        self, connection: Optional[Dict[str, Any]]
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if not connection:
            shop_id, owner_id = self._resolve_shop_and_owner()
            return shop_id, owner_id, settings.TELEGRAM_BOT_TOKEN or None
        shop_id = connection.get("shop_id")
        owner_id = None
        try:
            result = (
                supabase_client.table("shops")
                .select("owner_id")
                .eq("id", shop_id)
                .limit(1)
                .execute()
            )
            if result.data:
                owner_id = result.data[0].get("owner_id")
            if not owner_id:
                membership = (
                    supabase_client.table("shop_members")
                    .select("user_id")
                    .eq("shop_id", shop_id)
                    .eq("role", "owner")
                    .eq("status", "active")
                    .limit(1)
                    .execute()
                )
                if membership.data:
                    owner_id = membership.data[0].get("user_id")
            from app.services.telegram_connection_service import (
                telegram_connection_service,
            )

            bot_token = telegram_connection_service.resolve_token(connection)
        except Exception as exc:
            logger.error(
                "Telegram connection context failed connection_id=%s error_type=%s",
                connection.get("id"),
                type(exc).__name__,
            )
            return shop_id, owner_id, None
        return shop_id, owner_id, bot_token

    def get_or_create_customer(
        self,
        telegram_user_id: str,
        telegram_chat_id: str,
        shop_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not supabase_client:
            return None

        if shop_id:
            try:
                existing = (
                    supabase_client.table("customer_channels")
                    .select("*, customers(*)")
                    .eq("shop_id", shop_id)
                    .eq("channel", "telegram")
                    .eq("channel_user_id", telegram_user_id)
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    channel = existing.data[0]
                    customer = dict(channel.get("customers") or {})
                    customer.update(
                        {
                            "telegram_state": channel.get("state") or "awaiting_name",
                            "profile_completed": bool(channel.get("profile_completed")),
                            "telegram_user_id": telegram_user_id,
                            "telegram_chat_id": telegram_chat_id,
                            "_telegram_channel_id": channel.get("id"),
                        }
                    )
                    return customer

                customer_result = supabase_client.table("customers").insert(
                    {"shop_id": shop_id, "name": "Unknown"}
                ).execute()
                if not customer_result.data:
                    return None
                customer = customer_result.data[0]
                channel_result = supabase_client.table("customer_channels").insert(
                    {
                        "shop_id": shop_id,
                        "customer_id": customer["id"],
                        "channel": "telegram",
                        "channel_user_id": telegram_user_id,
                        "channel_chat_id": telegram_chat_id,
                        "state": "awaiting_name",
                        "profile_completed": False,
                    }
                ).execute()
                if not channel_result.data:
                    return None
                return {
                    **customer,
                    "telegram_state": "awaiting_name",
                    "profile_completed": False,
                    "telegram_user_id": telegram_user_id,
                    "telegram_chat_id": telegram_chat_id,
                    "_telegram_channel_id": channel_result.data[0]["id"],
                }
            except Exception as e:
                logger.error("Error in scoped Telegram customer lookup: %s", e)
                return None
            
        try:
            res = supabase_client.table("customers").select("*").eq("telegram_user_id", telegram_user_id).execute()
            if res.data:
                return res.data[0]
                
            # Create
            shop_id, _ = self._resolve_shop_and_owner()
            if not shop_id:
                return None
                
            new_customer = {
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": telegram_chat_id,
                "shop_id": shop_id,
                "name": "Unknown",
                "telegram_state": "awaiting_name",
                "profile_completed": False
            }
            create_res = supabase_client.table("customers").insert(new_customer).execute()
            if create_res.data:
                return create_res.data[0]
        except Exception as e:
            logger.error(f"Error in get_or_create_customer: {e}")
        return None

    def update_customer(
        self,
        customer_id: str,
        updates: Dict[str, Any],
        channel_id: Optional[str] = None,
    ):
        if not supabase_client:
            return
        try:
            customer_fields = {
                key: value
                for key, value in updates.items()
                if key not in {"telegram_state", "profile_completed"}
            }
            channel_fields = {}
            if "telegram_state" in updates:
                channel_fields["state"] = updates["telegram_state"]
            if "profile_completed" in updates:
                channel_fields["profile_completed"] = updates["profile_completed"]
            if customer_fields:
                supabase_client.table("customers").update(customer_fields).eq(
                    "id", customer_id
                ).execute()
            if channel_id and channel_fields:
                supabase_client.table("customer_channels").update(channel_fields).eq(
                    "id", channel_id
                ).execute()
            elif not channel_id and channel_fields:
                legacy_updates = {
                    "telegram_state": updates.get("telegram_state"),
                    "profile_completed": updates.get("profile_completed"),
                }
                supabase_client.table("customers").update(
                    {key: value for key, value in legacy_updates.items() if value is not None}
                ).eq("id", customer_id).execute()
        except Exception as e:
            logger.error(f"Error updating customer: {e}")

    async def process_update(
        self, payload: Dict[str, Any], connection: Optional[Dict[str, Any]] = None
    ):
        shop_id, owner_id, bot_token = self._resolve_connection_context(connection)
        if not shop_id or not owner_id or not bot_token:
            logger.warning(
                "Telegram update is not routable connection_id=%s",
                (connection or {}).get("id"),
            )
            return
        token_context = self._request_bot_token.set(bot_token)
        try:
            provider_namespace = str((connection or {}).get("id") or "legacy")
            return await self._process_update(
                payload,
                shop_id,
                owner_id,
                provider_namespace=provider_namespace,
                scoped_connection=bool(connection),
            )
        finally:
            self._request_bot_token.reset(token_context)

    async def _process_update(
        self,
        payload: Dict[str, Any],
        shop_id: str,
        owner_id: str,
        provider_namespace: str = "legacy",
        scoped_connection: bool = False,
    ):
        message = payload.get("message")
        if not message:
            return
            
        chat_id = str(message.get("chat", {}).get("id"))
        user_id = str(message.get("from", {}).get("id"))
        text = message.get("text", "").strip()
        # Support both voice and audio
        voice_or_audio = message.get("voice") or message.get("audio")
        
        customer = self.get_or_create_customer(
            user_id,
            chat_id,
            shop_id=shop_id if scoped_connection else None,
        )
        if not customer:
            self.send_message(chat_id, "System error initializing profile.")
            return

        def persist_customer(updates: Dict[str, Any]) -> None:
            self.update_customer(
                customer["id"],
                updates,
                channel_id=customer.get("_telegram_channel_id"),
            )

        if voice_or_audio:
            if not customer.get("profile_completed"):
                self.send_message(chat_id, "Please complete your profile setup first before sending voice orders.")
                return
                
            file_id = voice_or_audio.get("file_id")
            if not file_id:
                logger.warning("Telegram voice/audio missing file_id.")
                self.send_message(chat_id, "Sorry, I could not read the voice message.")
                return
            
            logger.info(f"Telegram voice/audio file_id present: {file_id}")
            
            bot_token = self._current_bot_token()
            if not bot_token:
                logger.error("No Telegram bot credential is available for media download.")
                self.send_message(chat_id, "Sorry, I could not download the voice message. Please try again or send text.")
                return

            try:
                # 1. Get file path
                file_info_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
                file_info_resp = requests.get(file_info_url, timeout=10)
                
                logger.info(f"Telegram getFile status_code: {file_info_resp.status_code}")
                
                if file_info_resp.status_code in (401, 404):
                    logger.error(f"Telegram getFile failed with {file_info_resp.status_code}. Token might be revoked or invalid.")
                    self.send_message(chat_id, "Sorry, I could not download the voice message. Please try again or send text.")
                    return
                
                file_info_resp.raise_for_status()
                
                resp_json = file_info_resp.json()
                if not resp_json.get("ok"):
                    # Safe logging: log error_code and description, DO NOT log the full url or token
                    err_code = resp_json.get("error_code")
                    desc = resp_json.get("description")
                    logger.error(f"Telegram getFile returned ok=false. error_code={err_code}, description={desc}")
                    self.send_message(chat_id, "Sorry, I could not download the voice message. Please try again or send text.")
                    return
                    
                file_path = resp_json.get("result", {}).get("file_path")
                if not file_path:
                    logger.error("Telegram getFile ok=true but missing result.file_path")
                    self.send_message(chat_id, "Sorry, I could not download the voice message. Please try again or send text.")
                    return
                    
                logger.info(f"Telegram getFile ok/file_path present.")
                    
                # 2. Download file
                download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                dl_resp = requests.get(download_url, timeout=20)
                logger.info(f"Telegram download status_code: {dl_resp.status_code}")
                
                if dl_resp.status_code != 200:
                    logger.error(f"Telegram file download failed with status {dl_resp.status_code}")
                    self.send_message(chat_id, "Sorry, I could not download the voice message. Please try again or send text.")
                    return
                    
                file_content = dl_resp.content
                logger.info(f"Telegram downloaded byte size: {len(file_content)}")
                
                from app.services.gemini import GeminiService
                filename = file_path.split("/")[-1] if "/" in file_path else "voice.ogg"
                ext = filename.split('.')[-1].lower() if '.' in filename else 'unknown'
                logger.info(f"Telegram temp file path extension: {ext}")
                
                mime_type = "application/octet-stream"
                if ext in ["ogg", "oga", "opus"]:
                    mime_type = "audio/ogg"
                elif ext == "wav":
                    mime_type = "audio/wav"
                elif ext == "mp3":
                    mime_type = "audio/mpeg"
                elif ext == "m4a":
                    mime_type = "audio/mp4"

                transcript = None
                try:
                    transcript = await GeminiService.transcribe_audio_file(file_content, filename, mime_type)
                except Exception as stt_err:
                    logger.warning(f"Gemini STT direct pass failed: {stt_err}. Trying ffmpeg fallback...")
                    if ext in ["ogg", "oga", "opus"]:
                        import tempfile
                        import subprocess
                        import os
                        
                        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f_in:
                            f_in.write(file_content)
                            f_in_path = f_in.name
                            
                        f_out_path = f_in_path + ".wav"
                        try:
                            subprocess.run(["ffmpeg", "-y", "-i", f_in_path, "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", f_out_path], check=True, capture_output=True)
                            with open(f_out_path, "rb") as f_out:
                                wav_content = f_out.read()
                                
                            transcript = await GeminiService.transcribe_audio_file(wav_content, "fallback.wav", "audio/wav")
                        except Exception as fallback_err:
                            logger.error(f"FFMPEG fallback failed: {fallback_err}")
                        finally:
                            if os.path.exists(f_in_path):
                                os.remove(f_in_path)
                            if os.path.exists(f_out_path):
                                os.remove(f_out_path)
                    
                    if not transcript:
                        logger.error("Gemini STT transcription failed after fallback.")
                        self.send_message(chat_id, "Sorry, voice order could not be processed. Please send the order as text.")
                        return

                if not transcript:
                    logger.error("Gemini STT transcription failed (returned empty).")
                    self.send_message(chat_id, "Sorry, voice order could not be processed. Please send the order as text.")
                    return
                    
                from app.services.intent_router import IntentRouter
                metadata = {
                    "source": "telegram",
                    "telegram_connection_id": (
                        provider_namespace if scoped_connection else None
                    ),
                    "telegram_user_id": user_id,
                    "telegram_chat_id": chat_id,
                    "customer_id": customer["id"],
                    "input_type": "voice",
                    "telegram_message_id": message.get("message_id")
                }

                telegram_message_id = message.get("message_id")
                if telegram_message_id is None:
                    logger.warning("Telegram voice message is missing message_id")
                    self.send_message(
                        chat_id, "I could not identify that message. Please resend it."
                    )
                    return
                provider_msg_id = (
                    f"{provider_namespace}:{chat_id}:{telegram_message_id}"
                    if scoped_connection
                    else f"{chat_id}_{telegram_message_id}"
                )
                from app.schemas.inbound import NormalizedInboundMessage
                msg_obj = NormalizedInboundMessage(
                    shop_id=shop_id,
                    customer_id=customer["id"],
                    channel="telegram",
                    provider_message_id=provider_msg_id,
                    message_type="voice",
                    raw_text=transcript,
                    metadata=metadata
                )
                result = await IntentRouter.process_inbound_message(msg_obj)

                if result.get("reply_message"):
                    self.send_message(chat_id, result["reply_message"])

            except Exception as e:
                # Sanitize error message in case it contains the URL
                err_str = str(e).replace(bot_token, "***TOKEN***") if bot_token else str(e)
                logger.error(f"Failed to process telegram voice order: {err_str}")
                self.send_message(chat_id, "Sorry, I could not process the voice message. Please try again or send text.")
            return
            
        if not text:
            return
            
        state = customer.get("telegram_state", "awaiting_name")
        
        # Handle commands
        if text.startswith("/start"):
            if customer.get("profile_completed"):
                self.send_message(chat_id, f"Welcome back, {customer.get('name')}. Send your order here.")
            else:
                persist_customer({"telegram_state": "awaiting_name"})
                self.send_message(chat_id, "Welcome to PhoneERP. Please tell me your name.")
            return
            
        if text.startswith("/help"):
            msg = "Send your order as text or voice.\nCommands:\n/profile - view your saved details\n/edit - update name, address, or phone\n/orders - view recent orders\n/cancel - cancel current profile edit"
            self.send_message(chat_id, msg)
            return
            
        if text.startswith("/cancel"):
            if state.startswith("editing_") or state.startswith("awaiting_"):
                new_state = "ready" if customer.get("profile_completed") else "awaiting_name"
                persist_customer({"telegram_state": new_state})
                self.send_message(chat_id, "Cancelled.")
            else:
                self.send_message(chat_id, "Nothing to cancel.")
            return
            
        if text.startswith("/edit") and not text.startswith("/edit_"):
            msg = "What do you want to edit?\n/edit_name\n/edit_address\n/edit_phone"
            self.send_message(chat_id, msg)
            return
            
        if text.startswith("/profile"):
            msg = f"Name: {customer.get('name')}\nAddress: {customer.get('default_address') or customer.get('address')}"
            if customer.get("phone"):
                msg += f"\nPhone: {customer.get('phone')}"
            msg += "\n\nUse /edit_name, /edit_address, or /edit_phone to change these."
            self.send_message(chat_id, msg)
            return
            
        if text.startswith("/edit_name"):
            persist_customer({"telegram_state": "editing_name"})
            self.send_message(chat_id, "Please reply with your new name.")
            return
            
        if text.startswith("/edit_address"):
            persist_customer({"telegram_state": "editing_address"})
            self.send_message(chat_id, "Please reply with your new delivery address.")
            return

        if text.startswith("/edit_phone"):
            persist_customer({"telegram_state": "editing_phone"})
            self.send_message(chat_id, "Please reply with your new 10-digit phone number, or type 'skip'.")
            return

        if text.startswith("/orders"):
            try:
                if not supabase_client:
                    self.send_message(chat_id, "Could not fetch orders right now. Database unavailable.")
                    return
                    
                resp = (
                    supabase_client.table("action_cards")
                    .select("id, status, created_at, items")
                    .eq("shop_id", shop_id)
                    .eq("customer_id", customer["id"])
                    .order("created_at", desc=True)
                    .limit(5)
                    .execute()
                )
                cards = resp.data or []
                
                if not cards:
                    resp = (
                        supabase_client.table("action_cards")
                        .select("id, status, created_at, items")
                        .eq("shop_id", shop_id)
                        .eq("metadata->>telegram_user_id", str(user_id))
                        .order("created_at", desc=True)
                        .limit(5)
                        .execute()
                    )
                    cards = resp.data or []
                    
                if not cards:
                    resp = (
                        supabase_client.table("action_cards")
                        .select("id, status, created_at, items")
                        .eq("shop_id", shop_id)
                        .eq("metadata->>telegram_chat_id", str(chat_id))
                        .order("created_at", desc=True)
                        .limit(5)
                        .execute()
                    )
                    cards = resp.data or []
                    
                if not cards:
                    self.send_message(chat_id, "No orders found yet.")
                    return
                
                msg_lines = ["Your recent orders:\n"]
                for c in cards:
                    short_id = c["id"][:8] if c.get("id") else "unknown"
                    dt = c.get("created_at", "").split("T")[0]
                    status = (c.get("status") or "pending").title()
                    
                    items = c.get("items") or []
                    item_summary = f"{len(items)} items"
                    if items:
                        names = [it.get("name", "Item") for it in items[:2] if isinstance(it, dict)]
                        item_summary = ", ".join(names) if names else f"{len(items)} items"
                        if len(items) > 2:
                            item_summary += f" + {len(items) - 2} more"
                            
                    msg_lines.append(f"• ID: {short_id}")
                    msg_lines.append(f"  Date: {dt}")
                    msg_lines.append(f"  Status: {status}")
                    msg_lines.append(f"  Items: {item_summary}\n")
                    
                self.send_message(chat_id, "\n".join(msg_lines))
            except Exception as e:
                logger.error(f"Failed to fetch telegram orders: {e}")
                self.send_message(chat_id, "Could not fetch orders right now.")
            return

        if text.startswith("/"):
            self.send_message(chat_id, "Unknown command. Use /help to see options.")
            return

        # State machine handling
        if state == "awaiting_name":
            persist_customer({"name": text, "telegram_state": "awaiting_address"})
            self.send_message(chat_id, "Thanks! What is your delivery address?")
            return
            
        if state == "awaiting_address":
            persist_customer({
                "default_address": text, 
                "address": text,
                "telegram_state": "awaiting_phone"
            })
            self.send_message(chat_id, "Please provide your phone number (or type 'skip').")
            return
            
        if state == "awaiting_phone":
            if text.lower() == "skip":
                persist_customer({"profile_completed": True, "telegram_state": "ready"})
                self.send_message(chat_id, "Profile saved. Now send your order.")
                return
            
            norm_phone = normalize_phone(text)
            if not norm_phone:
                self.send_message(chat_id, "Invalid phone number. Please send a valid 10-digit Indian number or type 'skip'.")
                return
                
            persist_customer({"phone": norm_phone, "profile_completed": True, "telegram_state": "ready"})
            self.send_message(chat_id, "Profile saved. Now send your order.")
            return
            
        if state == "editing_name":
            persist_customer({"name": text, "telegram_state": "ready"})
            self.send_message(chat_id, "Name updated!")
            return
            
        if state == "editing_address":
            persist_customer({
                "default_address": text,
                "address": text,
                "telegram_state": "ready"
            })
            self.send_message(chat_id, "Address updated!")
            return

        if state == "editing_phone":
            if text.lower() == "skip":
                persist_customer({"telegram_state": "ready"})
                self.send_message(chat_id, "Phone update skipped.")
                return
                
            norm_phone = normalize_phone(text)
            if not norm_phone:
                self.send_message(chat_id, "Invalid phone number. Please send a valid 10-digit Indian number or type 'skip'.")
                return
                
            persist_customer({"phone": norm_phone, "telegram_state": "ready"})
            self.send_message(chat_id, "Phone updated!")
            return

        # Handle normal text as order
        if not customer.get("profile_completed"):
            self.send_message(chat_id, "Please complete your profile setup first.")
            return
            
        try:
            from app.services.intent_router import IntentRouter
            metadata = {
                "source": "telegram",
                "telegram_connection_id": (
                    provider_namespace if scoped_connection else None
                ),
                "telegram_user_id": user_id,
                "telegram_chat_id": chat_id,
                "customer_id": customer["id"],
                "input_type": "text",
                "telegram_message_id": message.get("message_id")
        }
        
            telegram_message_id = message.get("message_id")
            if telegram_message_id is None:
                logger.warning("Telegram text message is missing message_id")
                self.send_message(
                    chat_id, "I could not identify that message. Please resend it."
                )
                return
            provider_msg_id = (
                f"{provider_namespace}:{chat_id}:{telegram_message_id}"
                if scoped_connection
                else f"{chat_id}_{telegram_message_id}"
            )
            from app.schemas.inbound import NormalizedInboundMessage
            msg_obj = NormalizedInboundMessage(
                shop_id=shop_id,
                customer_id=customer["id"],
                channel="telegram",
                provider_message_id=provider_msg_id,
                message_type="text",
                raw_text=text,
                metadata=metadata
            )
            result = await IntentRouter.process_inbound_message(msg_obj)

            if result.get("reply_message"):
                self.send_message(chat_id, result["reply_message"])

        except Exception as e:
            logger.error(f"Failed to process telegram text message: {e}")
            self.send_message(chat_id, "Message could not be processed. Please try again.")

telegram_service = TelegramService()
