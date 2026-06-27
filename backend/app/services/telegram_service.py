import logging
import requests
import re
from typing import Optional, Dict, Any
from app.config.settings import settings
from app.services.supabase import supabase_client
from app.controllers.action_card import ActionCardController

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
    
    def send_message(self, chat_id: str, text: str):
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set. Cannot send message.")
            return
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send telegram message: {e}")

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

    def get_or_create_customer(self, telegram_user_id: str, telegram_chat_id: str) -> Optional[Dict[str, Any]]:
        if not supabase_client:
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

    def update_customer(self, customer_id: str, updates: Dict[str, Any]):
        if not supabase_client:
            return
        try:
            supabase_client.table("customers").update(updates).eq("id", customer_id).execute()
        except Exception as e:
            logger.error(f"Error updating customer: {e}")

    async def process_update(self, payload: Dict[str, Any]):
        message = payload.get("message")
        if not message:
            return
            
        chat_id = str(message.get("chat", {}).get("id"))
        user_id = str(message.get("from", {}).get("id"))
        text = message.get("text", "").strip()
        # Support both voice and audio
        voice_or_audio = message.get("voice") or message.get("audio")
        
        shop_id, owner_id = self._resolve_shop_and_owner()
        if not shop_id or not owner_id:
            self.send_message(chat_id, "Shop is not configured yet. Please contact the shop owner.")
            return

        customer = self.get_or_create_customer(user_id, chat_id)
        if not customer:
            self.send_message(chat_id, "System error initializing profile.")
            return

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
            
            # Fetch token dynamically to support env var updates without restart
            bot_token = settings.TELEGRAM_BOT_TOKEN
            if not bot_token:
                logger.error("TELEGRAM_BOT_TOKEN is not configured.")
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
                    
                extracted = await GeminiService.extract_order_details(transcript)
                self._create_order_card(extracted, transcript, shop_id, owner_id, customer, user_id, chat_id, input_type="voice", message_id=message.get("message_id"))
                self.send_message(chat_id, "Order received. Shopkeeper will review.\nYou can check recent orders with /orders.")
            except Exception as e:
                # Sanitize error message in case it contains the URL
                err_str = str(e).replace(bot_token, "***TOKEN***") if bot_token else str(e)
                logger.error(f"Failed to process telegram voice order: {err_str}")
                self.send_message(chat_id, "Sorry, I could not download the voice message. Please try again or send text.")
            return
            
        if not text:
            return
            
        state = customer.get("telegram_state", "awaiting_name")
        
        # Handle commands
        if text.startswith("/start"):
            if customer.get("profile_completed"):
                self.send_message(chat_id, f"Welcome back, {customer.get('name')}. Send your grocery order here.")
            else:
                self.update_customer(customer["id"], {"telegram_state": "awaiting_name"})
                self.send_message(chat_id, "Welcome to PhoneERP. Please tell me your name.")
            return
            
        if text.startswith("/profile"):
            msg = f"Name: {customer.get('name')}\nAddress: {customer.get('default_address') or customer.get('address')}"
            if customer.get("phone"):
                msg += f"\nPhone: {customer.get('phone')}"
            msg += "\n\nUse /edit_name, /edit_address, or /edit_phone to change these."
            self.send_message(chat_id, msg)
            return
            
        if text.startswith("/edit_name"):
            self.update_customer(customer["id"], {"telegram_state": "editing_name"})
            self.send_message(chat_id, "Please reply with your new name.")
            return
            
        if text.startswith("/edit_address"):
            self.update_customer(customer["id"], {"telegram_state": "editing_address"})
            self.send_message(chat_id, "Please reply with your new delivery address.")
            return

        if text.startswith("/edit_phone"):
            self.update_customer(customer["id"], {"telegram_state": "editing_phone"})
            self.send_message(chat_id, "Please reply with your new 10-digit phone number, or type 'skip'.")
            return

        if text.startswith("/orders"):
            try:
                if not supabase_client:
                    self.send_message(chat_id, "Could not fetch orders right now. Database unavailable.")
                    return
                    
                resp = supabase_client.table("action_cards").select("id, status, created_at, items").eq("customer_id", customer["id"]).order("created_at", desc=True).limit(5).execute()
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

        # State machine handling
        if state == "awaiting_name":
            self.update_customer(customer["id"], {"name": text, "telegram_state": "awaiting_address"})
            self.send_message(chat_id, "Thanks! What is your delivery address?")
            return
            
        if state == "awaiting_address":
            self.update_customer(customer["id"], {
                "default_address": text, 
                "address": text,
                "telegram_state": "awaiting_phone"
            })
            self.send_message(chat_id, "Please provide your phone number (or type 'skip').")
            return
            
        if state == "awaiting_phone":
            if text.lower() == "skip":
                self.update_customer(customer["id"], {"profile_completed": True, "telegram_state": "ready"})
                self.send_message(chat_id, "Profile saved. Now send your order.")
                return
            
            norm_phone = normalize_phone(text)
            if not norm_phone:
                self.send_message(chat_id, "Invalid phone number. Please send a valid 10-digit Indian number or type 'skip'.")
                return
                
            self.update_customer(customer["id"], {"phone": norm_phone, "profile_completed": True, "telegram_state": "ready"})
            self.send_message(chat_id, "Profile saved. Now send your order.")
            return
            
        if state == "editing_name":
            self.update_customer(customer["id"], {"name": text, "telegram_state": "ready"})
            self.send_message(chat_id, "Name updated!")
            return
            
        if state == "editing_address":
            self.update_customer(customer["id"], {
                "default_address": text,
                "address": text,
                "telegram_state": "ready"
            })
            self.send_message(chat_id, "Address updated!")
            return

        if state == "editing_phone":
            if text.lower() == "skip":
                self.update_customer(customer["id"], {"telegram_state": "ready"})
                self.send_message(chat_id, "Phone update skipped.")
                return
                
            norm_phone = normalize_phone(text)
            if not norm_phone:
                self.send_message(chat_id, "Invalid phone number. Please send a valid 10-digit Indian number or type 'skip'.")
                return
                
            self.update_customer(customer["id"], {"phone": norm_phone, "telegram_state": "ready"})
            self.send_message(chat_id, "Phone updated!")
            return

        # Handle normal text as order
        if not customer.get("profile_completed"):
            self.send_message(chat_id, "Please complete your profile setup first.")
            return
            
        # Extract order using existing pipeline
        # Extract order using existing pipeline
        try:
            from app.services.gemini import GeminiService
            extracted = await GeminiService.extract_order_details(text)
            self._create_order_card(extracted, text, shop_id, owner_id, customer, user_id, chat_id, input_type="text", message_id=message.get("message_id"))
            self.send_message(chat_id, "Order received. Shopkeeper will review.\nYou can check recent orders with /orders.")
        except Exception as e:
            logger.error(f"Failed to process telegram text order: {e}")
            self.send_message(chat_id, "Order could not be created. Please try again.")

    def _create_order_card(self, extracted: Dict[str, Any], transcript: str, shop_id: str, owner_id: str, customer: Dict[str, Any], user_id: str, chat_id: str, input_type: str, message_id: Optional[int] = None):
        # Use profile fallbacks
        if not extracted.get("customer_name") or extracted.get("customer_name").lower() == "unknown":
            extracted["customer_name"] = customer.get("name")
        if not extracted.get("delivery_address") or extracted.get("delivery_address").lower() == "unknown":
            extracted["delivery_address"] = customer.get("default_address") or customer.get("address")
        
        # Phone fallback
        if not extracted.get("phone") and customer.get("phone"):
            extracted["phone"] = customer.get("phone")
        
        # Prepare card data
        from app.routes.endpoints import _safe_items_from_extracted
        safe_items = _safe_items_from_extracted(extracted, shop_id)
        
        card_data = {
            "shop_id": shop_id,
            "customer_id": customer["id"],
            "customer_name": extracted.get("customer_name"),
            "phone": extracted.get("phone"),
            "delivery_address": extracted.get("delivery_address"),
            "payment_method": extracted.get("payment_method", "UNKNOWN"),
            "items": [item.model_dump() for item in safe_items],
            "operations": extracted.get("operations", []),
            "status": "pending",
            "source": "telegram",
            "message_type": extracted.get("type", "ORDER"),
            "confidence": extracted.get("confidence", 0.0),
            "metadata": {
                "source": "telegram",
                "telegram_user_id": user_id,
                "telegram_chat_id": chat_id,
                "customer_id": customer["id"],
                "input_type": input_type,
                "pipeline": "gemini_gemini",
                "extraction_notes": extracted.get("extraction_notes", "")
            },
            "transcript": transcript
        }
        
        if message_id:
            card_data["metadata"]["telegram_message_id"] = message_id

        from app.services.confidence_scorer import ConfidenceScorer
        score, label, reasons = ConfidenceScorer.calculate_confidence(card_data)
        card_data["confidence_score"] = score
        card_data["confidence_label"] = label
        card_data["confidence_reasons"] = reasons

        # Create action card via controller directly to persist correctly with user_id
        ActionCardController.create_card(card_data, user_id=owner_id)

telegram_service = TelegramService()
