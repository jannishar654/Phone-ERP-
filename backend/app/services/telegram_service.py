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
        voice = message.get("voice")
        
        shop_id, owner_id = self._resolve_shop_and_owner()
        if not shop_id or not owner_id:
            self.send_message(chat_id, "Shop is not configured yet. Please contact the shop owner.")
            return

        customer = self.get_or_create_customer(user_id, chat_id)
        if not customer:
            self.send_message(chat_id, "System error initializing profile.")
            return

        if voice:
            if not customer.get("profile_completed"):
                self.send_message(chat_id, "Please complete your profile setup first before sending voice orders.")
                return
                
            file_id = voice.get("file_id")
            if not file_id:
                self.send_message(chat_id, "Sorry, I could not read the voice message.")
                return
            
            try:
                file_info_url = f"{self.api_url}/getFile?file_id={file_id}"
                file_info_resp = requests.get(file_info_url, timeout=10)
                file_info_resp.raise_for_status()
                file_path = file_info_resp.json().get("result", {}).get("file_path")
                if not file_path:
                    raise Exception("No file_path returned")
                    
                download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                dl_resp = requests.get(download_url, timeout=20)
                dl_resp.raise_for_status()
                file_content = dl_resp.content
                
                from app.services.gemini import GeminiService
                filename = file_path.split("/")[-1] if "/" in file_path else "voice.ogg"
                transcript = await GeminiService.transcribe_audio_file(file_content, filename)
                if not transcript:
                    self.send_message(chat_id, "Sorry, voice order could not be processed. Please send the order as text.")
                    return
                    
                extracted = await GeminiService.extract_order_details(transcript)
                self._create_order_card(extracted, transcript, shop_id, owner_id, customer, user_id, chat_id, input_type="voice", message_id=message.get("message_id"))
                self.send_message(chat_id, "Voice order received. Shopkeeper will review.")
            except Exception as e:
                logger.error(f"Failed to process telegram voice order: {e}")
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
            self.send_message(chat_id, "Order received. Shopkeeper will review.")
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
        card_data = {
            "shop_id": shop_id,
            "customer_id": customer["id"],
            "customer_name": extracted.get("customer_name"),
            "phone": extracted.get("phone"),
            "delivery_address": extracted.get("delivery_address"),
            "payment_method": extracted.get("payment_method", "UNKNOWN"),
            "items": extracted.get("items", []),
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
