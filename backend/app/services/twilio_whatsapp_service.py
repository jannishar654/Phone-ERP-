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
    if cleaned.startswith("whatsapp:"):
        cleaned = cleaned.replace("whatsapp:", "")
    if re.match(r'^\+91\d{10}$', cleaned):
        return cleaned
    if re.match(r'^91\d{10}$', cleaned):
        return '+' + cleaned
    if re.match(r'^\d{10}$', cleaned):
        return '+91' + cleaned
    return None

def looks_like_order(msg: str) -> bool:
    t = msg.lower()
    qty_words = ["kilo", "kg", "litre", "liter", "packet", "dabba", "bottle", "gram", "pcs", "piece"]
    hindi_nums = ["ek", "do", "teen", "char", "paanch", "chhe", "saat", "aath", "nau", "das", "gyarah", "barah", "pandrah", "bees", "pachas"]
    verbs = ["bhej dena", "bhejna", "chahiye", "order", "de dena", "deliver", "pahuncha dena", "bhej do", "dedo", "de do"]
    if any(char.isdigit() for char in t): return True
    if any(re.search(r'\b' + w + r'\b', t) for w in qty_words + hindi_nums): return True
    if any(v in t for v in verbs): return True
    return False

class TwilioWhatsappService:
    def _resolve_shop_and_owner(self) -> tuple[Optional[str], Optional[str]]:
        return settings.TWILIO_DEFAULT_SHOP_ID, settings.TWILIO_DEFAULT_OWNER_ID

    def _generate_twiml(self, message: str) -> str:
        return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{message}</Message></Response>'

    def get_or_create_customer(self, wa_id: str, from_phone: str) -> Optional[Dict[str, Any]]:
        if not supabase_client:
            return None
            
        shop_id, _ = self._resolve_shop_and_owner()
        if not shop_id:
            return None

        try:
            res = supabase_client.table("customer_channels").select("*, customers(*)").eq("channel", "whatsapp").eq("channel_user_id", wa_id).eq("shop_id", shop_id).execute()
            if res.data:
                return res.data[0]
            phone_norm = normalize_phone(from_phone)
            customer_id = None
            customer_data = None
            
            if phone_norm:
                cust_res = supabase_client.table("customers").select("*").eq("shop_id", shop_id).eq("phone", phone_norm).execute()
                if cust_res.data:
                    customer_data = cust_res.data[0]
                    customer_id = customer_data["id"]
                    
            if not customer_id:
                new_customer = {
                    "shop_id": shop_id,
                    "name": "Unknown",
                    "phone": phone_norm
                }
                create_cust_res = supabase_client.table("customers").insert(new_customer).execute()
                if not create_cust_res.data:
                    return None
                customer_data = create_cust_res.data[0]
                customer_id = customer_data["id"]
            
            new_channel = {
                "shop_id": shop_id,
                "customer_id": customer_id,
                "channel": "whatsapp",
                "channel_user_id": wa_id,
                "channel_chat_id": wa_id,
                "phone": phone_norm,
                "state": "awaiting_name",
                "profile_completed": False
            }
            create_chan_res = supabase_client.table("customer_channels").insert(new_channel).execute()
            if create_chan_res.data:
                chan_data = create_chan_res.data[0]
                chan_data["customers"] = customer_data
                return chan_data
        except Exception as e:
            logger.error(f"Error in get_or_create_customer for twilio whatsapp: {e}")
        return None

    def update_channel_state(self, channel_id: str, updates: Dict[str, Any]):
        if not supabase_client: return
        try:
            supabase_client.table("customer_channels").update(updates).eq("id", channel_id).execute()
        except Exception as e:
            logger.error(f"Error updating customer channel: {e}")

    def update_customer(self, customer_id: str, updates: Dict[str, Any]):
        if not supabase_client: return
        try:
            supabase_client.table("customers").update(updates).eq("id", customer_id).execute()
        except Exception as e:
            logger.error(f"Error updating customer: {e}")

    async def process_update(self, payload: Dict[str, Any]) -> str:
        body = payload.get("Body", "").strip()
        from_phone = payload.get("From", "")
        wa_id = payload.get("WaId", "")
        if not wa_id:
            wa_id = from_phone.replace("whatsapp:", "")
            
        media_url_0 = payload.get("MediaUrl0")
        media_content_type_0 = payload.get("MediaContentType0")
        msg_id = payload.get("MessageSid")
        
        shop_id, owner_id = self._resolve_shop_and_owner()
        if not shop_id or not owner_id:
            return self._generate_twiml("Shop is not configured yet. Please contact the shop owner.")

        channel_data = self.get_or_create_customer(wa_id, from_phone)
        if not channel_data:
            return self._generate_twiml("System error initializing profile.")

        customer = channel_data.get("customers", {})
        customer_id = customer.get("id")
        state = channel_data.get("state", "awaiting_name")
        
        async def check_pending_order(curr_channel_data):
            meta = curr_channel_data.get("metadata", {})
            pending_text = meta.get("pending_order_text")
            if pending_text:
                try:
                    from app.services.gemini import GeminiService
                    extracted = await GeminiService.extract_order_details(pending_text)
                    self._create_order_card(extracted, pending_text, shop_id, owner_id, curr_channel_data, customer, payload, input_type="text")
                    meta.pop("pending_order_text", None)
                    meta.pop("pending_order_message_id", None)
                    self.update_channel_state(curr_channel_data["id"], {"metadata": meta})
                    return True
                except Exception as e:
                    logger.error(f"Failed to process pending order: {e}")
            return False
        
        if media_url_0:
            if not channel_data.get("profile_completed"):
                return self._generate_twiml("Please complete your profile setup first before sending voice orders.")
            
            account_sid = settings.TWILIO_ACCOUNT_SID
            auth_token = settings.TWILIO_AUTH_TOKEN
            
            try:
                resp = requests.get(media_url_0, auth=(account_sid, auth_token), timeout=20)
                if resp.status_code != 200:
                    logger.error(f"Failed to download Twilio media: status {resp.status_code}")
                    return self._generate_twiml("Sorry, I could not download the voice message. Please try again or send text.")
                
                file_content = resp.content
                mime_type = media_content_type_0 or "application/octet-stream"
                ext = "ogg" if "ogg" in mime_type else "wav" if "wav" in mime_type else "unknown"
                filename = f"voice.{ext}"
                
                from app.services.gemini import GeminiService
                transcript = None
                try:
                    transcript = await GeminiService.transcribe_audio_file(file_content, filename, mime_type)
                except Exception as stt_err:
                    logger.warning(f"Gemini STT direct pass failed: {stt_err}. Trying ffmpeg fallback...")
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
                        if os.path.exists(f_in_path): os.remove(f_in_path)
                        if os.path.exists(f_out_path): os.remove(f_out_path)
                        
                if not transcript:
                    return self._generate_twiml("Sorry, voice order could not be processed. Please send the order as text.")
                    
                extracted = await GeminiService.extract_order_details(transcript)
                self._create_order_card(extracted, transcript, shop_id, owner_id, channel_data, customer, payload, input_type="voice")
                return self._generate_twiml("Order received. Shopkeeper will review.")
            except Exception as e:
                logger.error(f"Failed to process twilio voice order: {e}")
                return self._generate_twiml("Sorry, I could not process the voice message. Please try again or send text.")

        if not body:
            return self._generate_twiml("")

        text = body.strip()
        t_lower = text.lower()
        
        if t_lower in ["hi", "hello", "/start"]:
            if channel_data.get("profile_completed"):
                return self._generate_twiml(f"Welcome back, {customer.get('name')}. Send your grocery order here.")
            else:
                self.update_channel_state(channel_data["id"], {"state": "awaiting_name"})
                return self._generate_twiml("Welcome to PhoneERP. Please tell me your name.")

        if t_lower in ["/help", "help"]:
            msg = "Send your grocery order as text or voice.\nCommands:\n/profile - view your saved details\n/edit - update name, address, or phone\n/orders - view recent orders\n/cancel - cancel current profile edit"
            return self._generate_twiml(msg)

        if t_lower in ["/cancel", "cancel"]:
            if state.startswith("editing_") or state.startswith("awaiting_"):
                new_state = "ready" if channel_data.get("profile_completed") else "awaiting_name"
                self.update_channel_state(channel_data["id"], {"state": new_state})
                return self._generate_twiml("Cancelled.")
            else:
                return self._generate_twiml("Nothing to cancel.")

        if t_lower in ["/edit", "edit"]:
            msg = "What do you want to edit?\n/edit_name\n/edit_address\n/edit_phone"
            return self._generate_twiml(msg)

        if t_lower in ["/profile", "profile"]:
            msg = f"Name: {customer.get('name')}\nAddress: {customer.get('address')}"
            if customer.get("phone"):
                msg += f"\nPhone: {customer.get('phone')}"
            msg += "\n\nUse /edit_name, /edit_address, or /edit_phone to change these."
            return self._generate_twiml(msg)

        if t_lower in ["/edit_name", "edit name"]:
            self.update_channel_state(channel_data["id"], {"state": "editing_name"})
            return self._generate_twiml("Please reply with your new name.")

        if t_lower in ["/edit_address", "edit address"]:
            self.update_channel_state(channel_data["id"], {"state": "editing_address"})
            return self._generate_twiml("Please reply with your new delivery address.")

        if t_lower in ["/edit_phone", "edit phone"]:
            self.update_channel_state(channel_data["id"], {"state": "editing_phone"})
            return self._generate_twiml("Please reply with your new 10-digit phone number, or type 'skip'.")

        if t_lower in ["/orders", "orders"]:
            try:
                if not supabase_client:
                    return self._generate_twiml("Could not fetch orders right now.")
                    
                resp = supabase_client.table("action_cards").select("id, status, created_at, items").eq("customer_id", customer["id"]).order("created_at", desc=True).limit(5).execute()
                cards = resp.data or []
                
                if not cards:
                    return self._generate_twiml("No orders found yet.")
                
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
                        if len(items) > 2: item_summary += f" + {len(items) - 2} more"
                    msg_lines.append(f"• ID: {short_id}\n  Date: {dt}\n  Status: {status}\n  Items: {item_summary}\n")
                    
                return self._generate_twiml("\n".join(msg_lines))
            except Exception as e:
                logger.error(f"Failed to fetch twilio orders: {e}")
                return self._generate_twiml("Could not fetch orders right now.")

        if not channel_data.get("profile_completed"):
            if looks_like_order(text):
                meta = channel_data.get("metadata", {})
                if msg_id and meta.get("pending_order_message_id") == msg_id:
                    return self._generate_twiml("") # ignore duplicate
                    
                from app.services.gemini import GeminiService
                extracted = await GeminiService.extract_order_details(text)
                
                ext_name = extracted.get("customer_name")
                ext_address = extracted.get("delivery_address")
                has_name = bool(ext_name and ext_name.lower() != "unknown")
                has_address = bool(ext_address and ext_address.lower() != "unknown")
                
                if has_name: customer["name"] = ext_name
                if has_address: customer["address"] = ext_address
                
                if has_name and has_address:
                    self.update_customer(customer_id, {"name": ext_name, "address": ext_address})
                    updates = {"display_name": ext_name, "state": "ready"}
                    if channel_data.get("phone"):
                        updates["profile_completed"] = True
                    self.update_channel_state(channel_data["id"], updates)
                    channel_data.update(updates)
                    
                    self._create_order_card(extracted, text, shop_id, owner_id, channel_data, customer, payload, input_type="text")
                    return self._generate_twiml("Order received. Shopkeeper will review.")
                else:
                    meta["pending_order_text"] = text
                    if msg_id:
                        meta["pending_order_message_id"] = msg_id
                    updates = {"metadata": meta}
                    
                    if has_name and state == "awaiting_name":
                        state = "awaiting_address"
                        self.update_customer(customer_id, {"name": ext_name})
                        updates["display_name"] = ext_name
                    
                    updates["state"] = state
                    self.update_channel_state(channel_data["id"], updates)
                    
                    if state == "awaiting_name":
                        return self._generate_twiml("Welcome to PhoneERP. Please tell me your name.")
                    elif state == "awaiting_address":
                        return self._generate_twiml("Thanks! What is your delivery address?")
            else:
                # Normal onboarding flow for non-orders
                if state == "awaiting_name":
                    self.update_customer(customer_id, {"name": text})
                    updates = {"display_name": text, "state": "awaiting_address"}
                    self.update_channel_state(channel_data["id"], updates)
                    channel_data.update(updates)
                    customer["name"] = text
                    return self._generate_twiml("Thanks! What is your delivery address?")
                    
                if state == "awaiting_address":
                    self.update_customer(customer_id, {"address": text})
                    updates = {}
                    if channel_data.get("phone"):
                        updates["state"] = "ready"
                        updates["profile_completed"] = True
                        self.update_channel_state(channel_data["id"], updates)
                        channel_data.update(updates)
                        customer["address"] = text
                        processed = await check_pending_order(channel_data)
                        msg = "Order received. Shopkeeper will review." if processed else "Profile saved. Now send your order."
                        return self._generate_twiml(msg)
                    else:
                        updates["state"] = "awaiting_phone"
                        self.update_channel_state(channel_data["id"], updates)
                        return self._generate_twiml("Please provide your phone number (or type 'skip').")
                        
                if state == "awaiting_phone":
                    updates = {"state": "ready", "profile_completed": True}
                    if text.lower() != "skip":
                        norm_phone = normalize_phone(text)
                        if not norm_phone:
                            return self._generate_twiml("Invalid phone number. Please send a valid 10-digit Indian number or type 'skip'.")
                        self.update_customer(customer_id, {"phone": norm_phone})
                        updates["phone"] = norm_phone
                        customer["phone"] = norm_phone
                        
                    self.update_channel_state(channel_data["id"], updates)
                    channel_data.update(updates)
                    processed = await check_pending_order(channel_data)
                    msg = "Order received. Shopkeeper will review." if processed else "Profile saved. Now send your order."
                    return self._generate_twiml(msg)

        if state == "editing_name":
            self.update_customer(customer_id, {"name": text})
            self.update_channel_state(channel_data["id"], {"display_name": text, "state": "ready"})
            return self._generate_twiml("Name updated!")
            
        if state == "editing_address":
            self.update_customer(customer_id, {"address": text})
            self.update_channel_state(channel_data["id"], {"state": "ready"})
            return self._generate_twiml("Address updated!")

        if state == "editing_phone":
            if text.lower() == "skip":
                self.update_channel_state(channel_data["id"], {"state": "ready"})
                return self._generate_twiml("Phone update skipped.")
                
            norm_phone = normalize_phone(text)
            if not norm_phone:
                return self._generate_twiml("Invalid phone number. Please send a valid 10-digit Indian number or type 'skip'.")
                
            self.update_customer(customer_id, {"phone": norm_phone})
            self.update_channel_state(channel_data["id"], {"phone": norm_phone, "state": "ready"})
            return self._generate_twiml("Phone updated!")
            
        try:
            from app.services.gemini import GeminiService
            extracted = await GeminiService.extract_order_details(text)
            self._create_order_card(extracted, text, shop_id, owner_id, channel_data, customer, payload, input_type="text")
            return self._generate_twiml("Order received. Shopkeeper will review.")
        except Exception as e:
            logger.error(f"Failed to process twilio text order: {e}")
            return self._generate_twiml("Order could not be created. Please try again.")

    def _create_order_card(self, extracted: Dict[str, Any], transcript: str, shop_id: str, owner_id: str, channel_data: Dict[str, Any], customer: Dict[str, Any], payload: Dict[str, Any], input_type: str):
        if not extracted.get("customer_name") or extracted.get("customer_name").lower() == "unknown":
            extracted["customer_name"] = customer.get("name")
        if not extracted.get("delivery_address") or extracted.get("delivery_address").lower() == "unknown":
            extracted["delivery_address"] = customer.get("default_address") or customer.get("address")
        if not extracted.get("customer_phone") and customer.get("phone"):
            extracted["customer_phone"] = customer.get("phone")
        if not extracted.get("customer_phone") and channel_data.get("phone"):
            extracted["customer_phone"] = channel_data.get("phone")
        
        from app.routes.endpoints import _safe_items_from_extracted
        safe_items = _safe_items_from_extracted(extracted, shop_id)
        
        from app.services.time_parser import parse_delivery_time
        raw_dt = extracted.get("delivery_time_raw") or extracted.get("delivery_time") or ""
        time_text = transcript if not raw_dt else raw_dt
        time_data = parse_delivery_time(time_text)
        
        delivery_time_normalized = time_data.get("normalized")
        delivery_time_confidence = time_data.get("confidence", 0.0)
        delivery_time_warning = time_data.get("warning")
        final_delivery_time = delivery_time_normalized or raw_dt
        
        card_data = {
            "shop_id": shop_id,
            "customer_id": customer["id"],
            "customer_name": extracted.get("customer_name"),
            "customer_phone": extracted.get("customer_phone"),
            "delivery_address": extracted.get("delivery_address"),
            "delivery_time": final_delivery_time,
            "delivery_time_raw": raw_dt,
            "delivery_time_normalized": delivery_time_normalized,
            "delivery_time_confidence": delivery_time_confidence,
            "delivery_time_warning": delivery_time_warning,
            "payment_method": extracted.get("payment_method", "UNKNOWN"),
            "items": [item.model_dump() for item in safe_items],
            "operations": extracted.get("operations", []),
            "status": "pending",
            "source": "whatsapp",
            "message_type": extracted.get("type", "ORDER"),
            "confidence": extracted.get("confidence", 0.0),
            "metadata": {
                "source": "whatsapp",
                "input_channel": "whatsapp",
                "whatsapp_wa_id": channel_data.get("channel_user_id"),
                "whatsapp_from": payload.get("From"),
                "twilio_message_sid": payload.get("MessageSid"),
                "customer_id": customer["id"],
                "input_type": input_type,
                "pipeline": "gemini_gemini",
                "extraction_notes": extracted.get("extraction_notes", ""),
                "original_delivery_time": raw_dt
            },
            "transcript": transcript
        }
        
        from app.services.confidence_scorer import ConfidenceScorer
        score, label, reasons = ConfidenceScorer.calculate_confidence(card_data)
        card_data["confidence_score"] = score
        card_data["confidence_label"] = label
        card_data["confidence_reasons"] = reasons

        ActionCardController.create_card(card_data, user_id=owner_id)

twilio_whatsapp_service = TwilioWhatsappService()
