import logging
import requests
from typing import Optional, Dict, Any
from app.config.settings import settings
from app.services.supabase import supabase_client
from app.controllers.action_card import ActionCardController

logger = logging.getLogger(__name__)

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
        
        if voice:
            self.send_message(chat_id, "Voice order support is coming soon. Please send your order as text for now.")
            return
            
        if not text:
            return

        shop_id, owner_id = self._resolve_shop_and_owner()
        if not shop_id or not owner_id:
            self.send_message(chat_id, "Shop is not configured yet. Please contact the shop owner.")
            return

        customer = self.get_or_create_customer(user_id, chat_id)
        if not customer:
            self.send_message(chat_id, "System error initializing profile.")
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
            msg = f"Name: {customer.get('name')}\nAddress: {customer.get('default_address') or customer.get('address')}\n\nUse /edit_name or /edit_address to change these."
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

        # State machine handling
        if state == "awaiting_name":
            self.update_customer(customer["id"], {"name": text, "telegram_state": "awaiting_address"})
            self.send_message(chat_id, "Thanks! What is your delivery address?")
            return
            
        if state == "awaiting_address":
            self.update_customer(customer["id"], {
                "default_address": text, 
                "address": text,
                "profile_completed": True, 
                "telegram_state": "ready"
            })
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

        # Handle normal text as order
        if not customer.get("profile_completed"):
            self.send_message(chat_id, "Please complete your profile setup first.")
            return
            
        # Extract order using existing pipeline
        try:
            from app.services.gemini import GeminiService
            extracted = await GeminiService.extract_order_details(text)
            
            # Use profile fallbacks
            if not extracted.get("customer_name") or extracted.get("customer_name").lower() == "unknown":
                extracted["customer_name"] = customer.get("name")
            if not extracted.get("delivery_address") or extracted.get("delivery_address").lower() == "unknown":
                extracted["delivery_address"] = customer.get("default_address") or customer.get("address")
            
            # Prepare card data
            card_data = {
                "shop_id": shop_id,
                "customer_id": customer["id"],
                "customer_name": extracted.get("customer_name"),
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
                    "extraction_notes": extracted.get("extraction_notes", "")
                },
                "transcript": text
            }

            from app.services.confidence_scorer import ConfidenceScorer
            score, label, reasons = ConfidenceScorer.calculate_confidence(card_data)
            card_data["confidence_score"] = score
            card_data["confidence_label"] = label
            card_data["confidence_reasons"] = reasons

            # Create action card via controller directly to persist correctly with user_id
            ActionCardController.create_card(card_data, user_id=owner_id)
            
            self.send_message(chat_id, "Order received. Shopkeeper will review.")
        except Exception as e:
            logger.error(f"Failed to process telegram order: {e}")
            self.send_message(chat_id, "Sorry, there was an issue processing your order. Please try again.")

telegram_service = TelegramService()
