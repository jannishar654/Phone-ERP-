from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime
import hashlib
from pydantic import BaseModel
from app.schemas.order import OrderResponse, OrderLifecycleUpdate
from app.schemas.access import StaffAccessValidateRequest, StaffAccessValidateResponse
from app.services.supabase import supabase_client
# Optional: if you have a dependency for staff auth:
# from app.dependencies.staff_auth import get_staff_context

router = APIRouter(prefix="/staff", tags=["Staff"])

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def get_staff_access_by_token(token: str):
    token_hash = hash_token(token)
    res = supabase_client.table("shop_staff_access").select("*").eq("token_hash", token_hash).is_("revoked_at", "null").execute()
    if not res.data:
        return None
        
    access = res.data[0]
    
    if access.get("expires_at"):
        expires_at = datetime.fromisoformat(access["expires_at"].replace('Z', '+00:00'))
        if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
            return None
            
    return access

@router.post("/validate", response_model=StaffAccessValidateResponse)
def validate_staff_access(req: StaffAccessValidateRequest):
    access = get_staff_access_by_token(req.token)
    if not access:
        return StaffAccessValidateResponse(valid=False)
        
    return StaffAccessValidateResponse(
        valid=True,
        shop_id=access["shop_id"],
        role=access["role"],
        expires_at=access.get("expires_at")
    )

class StaffOrderRequest(BaseModel):
    token: Optional[str] = None

def get_staff_context(token: Optional[str], user_id: Optional[str]):
    # Try session first
    if user_id:
        mem_res = supabase_client.table("shop_members").select("*").eq("user_id", user_id).eq("status", "active").execute()
        if mem_res.data:
            member = mem_res.data[0]
            return {"shop_id": member["shop_id"], "role": member["role"]}
        # Check owner fallback
        shop_res = supabase_client.table("shops").select("id").eq("owner_id", user_id).execute()
        if shop_res.data:
            return {"shop_id": shop_res.data[0]["id"], "role": "owner"}
    
    # Try token fallback
    if token:
        access = get_staff_access_by_token(token)
        if access:
            return {"shop_id": access["shop_id"], "role": access["role"]}
            
    return None

from app.dependencies.auth import get_optional_user_id

@router.post("/orders/packing", response_model=List[OrderResponse])
def get_packing_orders(req: StaffOrderRequest, user_id: Optional[str] = Depends(get_optional_user_id)):
    ctx = get_staff_context(req.token, user_id)
    if not ctx or ctx["role"] not in ["owner", "packer"]:
        raise HTTPException(status_code=403, detail="Invalid token or insufficient permissions")
        
    res = supabase_client.table("orders").select("*, order_items(*)").eq("shop_id", ctx["shop_id"]).eq("lifecycle_status", "packing").order("created_at", desc=False).execute()
    return res.data if res.data else []

@router.post("/orders/delivery", response_model=List[OrderResponse])
def get_delivery_orders(req: StaffOrderRequest, user_id: Optional[str] = Depends(get_optional_user_id)):
    ctx = get_staff_context(req.token, user_id)
    if not ctx or ctx["role"] not in ["owner", "delivery"]:
        raise HTTPException(status_code=403, detail="Invalid token or insufficient permissions")
        
    res = supabase_client.table("orders").select("*, order_items(*)").eq("shop_id", ctx["shop_id"]).eq("lifecycle_status", "out_for_delivery").order("created_at", desc=False).execute()
    return res.data if res.data else []

class UpdateLifecycleStatusStaff(BaseModel):
    token: Optional[str] = None
    lifecycle_status: str

@router.post("/orders/{order_id}/status", response_model=OrderResponse)
def staff_update_order_status(order_id: str, data: UpdateLifecycleStatusStaff, user_id: Optional[str] = Depends(get_optional_user_id)):
    ctx = get_staff_context(data.token, user_id)
    if not ctx:
        raise HTTPException(status_code=401, detail="Invalid token or session")
        
    new_status = data.lifecycle_status
    role = ctx["role"]
    shop_id = ctx["shop_id"]
    
    # Packer can only move to out_for_delivery
    if role == "packer" and new_status != "out_for_delivery":
        raise HTTPException(status_code=403, detail="Packers can only mark orders as out_for_delivery")
        
    # Delivery can only move to delivered or cancelled
    if role == "delivery" and new_status not in ["delivered", "cancelled"]:
        raise HTTPException(status_code=403, detail="Delivery staff can only mark orders as delivered or cancelled")
        
    res = supabase_client.table("orders").select("*").eq("id", order_id).eq("shop_id", shop_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order = res.data[0]
    current_status = order.get("lifecycle_status")
    
    # Validate transition
    if role == "packer":
        if current_status != "packing":
            raise HTTPException(status_code=400, detail="Order must be in packing status")
    if role == "delivery":
        if current_status != "out_for_delivery":
            raise HTTPException(status_code=400, detail="Order must be in out_for_delivery status")
            
    updates = {"lifecycle_status": new_status}
    now_iso = datetime.utcnow().isoformat()
    if new_status == "out_for_delivery":
        updates["out_for_delivery_at"] = now_iso
    elif new_status == "delivered":
        updates["delivered_at"] = now_iso
    elif new_status == "cancelled":
        updates["cancelled_at"] = now_iso
        
    update_res = supabase_client.table("orders").update(updates).eq("id", order_id).execute()
    if not update_res.data:
        raise HTTPException(status_code=500, detail="Failed to update order")
        
    # Send notification if delivered
    notification_info = {}
    if new_status == "delivered":
        notification_info = {
            "notification_sent": False,
            "notification_channel": None,
            "notification_sid": None,
            "notification_status": None,
            "notification_error": None
        }
        try:
            order_id_str = str(order_id)
            customer_id = order.get("customer_id")
            if customer_id:
                # Find customer channels
                channels_res = supabase_client.table("customer_channels").select("*").eq("customer_id", customer_id).execute()
                channels = channels_res.data if channels_res.data else []
                
                # Use deterministic HMAC token
                from app.utils.security import generate_deterministic_bill_token, hash_token
                from app.config.settings import settings
                from datetime import timedelta
                
                raw_token = generate_deterministic_bill_token(order_id_str, shop_id)
                token_hash = hash_token(raw_token)
                expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
                
                # Check if it exists, if so update it, else insert
                link_res = supabase_client.table("order_public_links").select("id").eq("order_id", order_id_str).execute()
                if link_res.data:
                    supabase_client.table("order_public_links").update({
                        "token_hash": token_hash,
                        "expires_at": expires_at
                    }).eq("id", link_res.data[0]["id"]).execute()
                else:
                    supabase_client.table("order_public_links").insert({
                        "order_id": order_id_str,
                        "shop_id": shop_id,
                        "token_hash": token_hash,
                        "expires_at": expires_at
                    }).execute()
                
                # Get frontend base URL
                base_url = getattr(settings, "FRONTEND_PUBLIC_BASE_URL", "http://localhost:3000")
                bill_url = f"{base_url}/bill/{raw_token}"
                total_amount = order.get("total_amount", 0)
                bill_msg = f"Your order has been delivered.\nTotal: ₹{total_amount}\nBill: {bill_url}"
                
                # Determine source and fallback channels
                notification_info["notification_attempted"] = True
                
                source = None
                card_phone = None
                telegram_chat_id = None
                
                action_card_id = order.get("action_card_id")
                if action_card_id:
                    card_res = supabase_client.table("action_cards").select("source, customer_phone, metadata").eq("id", action_card_id).execute()
                    if card_res.data:
                        card_data = card_res.data[0]
                        source = card_data.get("source")
                        card_phone = card_data.get("customer_phone")
                        meta = card_data.get("metadata") or {}
                        if source == "telegram":
                            telegram_chat_id = meta.get("telegram_chat_id")
                            
                whatsapp_channel = None
                telegram_channel = None
                
                for ch in channels:
                    if ch.get("channel") == "whatsapp":
                        whatsapp_channel = ch
                    elif ch.get("channel") == "telegram":
                        telegram_channel = ch
                        
                channel_to_use = source
                if not channel_to_use:
                    if telegram_channel: channel_to_use = "telegram"
                    elif whatsapp_channel: channel_to_use = "whatsapp"
                    elif order.get("customer_phone"): channel_to_use = "whatsapp"
                    
                print("DELIVERY_NOTIFICATION_DEBUG", {
                    "order_id": order_id_str,
                    "new_status": new_status,
                    "customer_id": customer_id,
                    "customer_phone_present": bool(order.get("customer_phone")),
                    "channels_count": len(channels),
                    "channel_names": [c.get("channel") for c in channels],
                    "has_twilio_env": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_WHATSAPP_FROM),
                    "has_telegram_env": bool(settings.TELEGRAM_BOT_TOKEN),
                    "has_frontend_url": bool(settings.FRONTEND_PUBLIC_BASE_URL),
                })
                
                if channel_to_use == "telegram":
                    chat_id = (telegram_channel.get("channel_chat_id") if telegram_channel else None) or telegram_chat_id
                    if chat_id:
                        try:
                            from app.services.telegram_service import telegram_service
                            telegram_service.send_message(chat_id, bill_msg)
                            notification_info["notification_sent"] = True
                            notification_info["notification_channel"] = "telegram"
                            print(f"DELIVERY_NOTIFICATION_SENT channel=telegram chat_id={chat_id}")
                        except Exception as e:
                            notification_info["notification_error"] = str(e)
                            print(f"DELIVERY_NOTIFICATION_FAILED safe_error={str(e)}")
                    else:
                        notification_info["notification_error"] = "No Telegram chat ID found"
                        print("DELIVERY_NOTIFICATION_SKIPPED reason=no_telegram_chat_id")
                        
                elif channel_to_use == "whatsapp":
                    phone_to_use = (whatsapp_channel.get("phone") if whatsapp_channel else None) or order.get("customer_phone") or card_phone
                    if not phone_to_use and customer_id:
                        cust_res = supabase_client.table("customers").select("phone").eq("id", customer_id).execute()
                        if cust_res.data: phone_to_use = cust_res.data[0].get("phone")
                        
                    if phone_to_use:
                        try:
                            from app.services.twilio_whatsapp_service import twilio_whatsapp_service
                            result = twilio_whatsapp_service.send_whatsapp_message(phone_to_use, bill_msg)
                            notification_info["notification_sent"] = result.get("sent", False)
                            notification_info["notification_channel"] = "whatsapp"
                            notification_info["notification_sid"] = result.get("sid")
                            if result.get("error"):
                                notification_info["notification_error"] = result.get("error")
                                print(f"DELIVERY_NOTIFICATION_FAILED safe_error={result.get('error')}")
                            else:
                                print(f"DELIVERY_NOTIFICATION_SENT channel=whatsapp sid={result.get('sid')}")
                        except Exception as e:
                            notification_info["notification_error"] = str(e)
                            print(f"DELIVERY_NOTIFICATION_FAILED safe_error={str(e)}")
                    else:
                        notification_info["notification_error"] = "No customer phone found"
                        print("DELIVERY_NOTIFICATION_SKIPPED reason=no_whatsapp_phone")
                else:
                    notification_info["notification_error"] = "No notification channel identified"
                    print("DELIVERY_NOTIFICATION_SKIPPED reason=no_channel_identified")
        except Exception as e:
            print(f"Warning: Failed to process delivery notifications: {str(e)}")
            
    final_res = supabase_client.table("orders").select("*, order_items(*)").eq("id", order_id).execute()
    final_data = final_res.data[0]
    if new_status == "delivered":
        final_data.update(notification_info)
        
    return final_data
