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
    lifecycle_status: Optional[str] = None
    status: Optional[str] = None
    lifecycleStatus: Optional[str] = None

@router.post("/orders/{order_id}/status", response_model=OrderResponse)
def staff_update_order_status(order_id: str, data: UpdateLifecycleStatusStaff, user_id: Optional[str] = Depends(get_optional_user_id)):
    ctx = get_staff_context(data.token, user_id)
    if not ctx:
        raise HTTPException(status_code=401, detail="Invalid token or session")
        
    new_status = data.lifecycle_status or data.status or data.lifecycleStatus
    if not new_status:
        raise HTTPException(status_code=422, detail="Missing status field")
        
    role = ctx["role"]
    shop_id = ctx["shop_id"]
    
    print(f"STAFF_STATUS_UPDATE_RECEIVED order_id={order_id} role={role} payload_status={new_status}", flush=True)
    
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
    
    print(f"STAFF_STATUS_UPDATE_RECEIVED order_id={order_id} role={role} payload_status={new_status} current_status={current_status}", flush=True)
    
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
        
    final_order = update_res.data[0]
    final_lifecycle_status = final_order.get("lifecycle_status")
    
    print(f"STAFF_STATUS_UPDATE_APPLIED order_id={order_id} new_status={final_lifecycle_status}", flush=True)
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"STAFF_STATUS_UPDATE_APPLIED order_id={order_id} new_status={final_lifecycle_status}")
    
    # Send notification if delivered
    notification_info = {}
    print(f"STAFF_STATUS_DELIVERED_BRANCH_CHECK new_status={final_lifecycle_status} is_delivered={final_lifecycle_status == 'delivered'}", flush=True)
    logger.warning(f"STAFF_STATUS_DELIVERED_BRANCH_CHECK new_status={final_lifecycle_status} is_delivered={final_lifecycle_status == 'delivered'}")
    
    if final_lifecycle_status == "delivered":
        notification_info = {
            "notification_attempted": True,
            "notification_sent": False,
            "notification_channel": "none",
            "notification_sid": None,
            "notification_status": None,
            "notification_error": None
        }
        try:
            print(f"DELIVERY_NOTIFICATION_ENTERED order_id={order_id}", flush=True)
            logger.warning(f"DELIVERY_NOTIFICATION_ENTERED order_id={order_id}")
            
            # Fetch full order
            full_order_res = supabase_client.table("orders").select("*").eq("id", order_id).execute()
            full_order = full_order_res.data[0] if full_order_res.data else final_order
            
            from app.utils.security import generate_deterministic_bill_token, hash_token
            from app.config.settings import settings
            from datetime import timedelta
            
            debug_info = {
                "order_id": order_id,
                "has_full_order": bool(full_order_res.data),
                "order_keys": list(full_order.keys()) if full_order else [],
                "customer_id_present": bool(full_order.get("customer_id")),
                "shop_id_present": bool(full_order.get("shop_id")),
                "customer_phone_present": bool(full_order.get("customer_phone")),
                "action_card_id_present": bool(full_order.get("action_card_id")),
                "total_amount_present": bool(full_order.get("total_amount")),
                "has_twilio_env": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_WHATSAPP_FROM),
                "has_telegram_env": bool(settings.TELEGRAM_BOT_TOKEN),
                "has_frontend_url": bool(settings.FRONTEND_PUBLIC_BASE_URL)
            }
            print(f"DELIVERY_NOTIFICATION_DEBUG {debug_info}", flush=True)
            logger.warning(f"DELIVERY_NOTIFICATION_DEBUG {debug_info}")
            
            order_id_str = str(order_id)
            customer_id = full_order.get("customer_id")
            shop_id_val = full_order.get("shop_id") or shop_id
            
            # Generate bill link
            
            raw_token = generate_deterministic_bill_token(order_id_str, shop_id_val)
            token_hash = hash_token(raw_token)
            expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
            
            link_res = supabase_client.table("order_public_links").select("id").eq("order_id", order_id_str).execute()
            if link_res.data:
                supabase_client.table("order_public_links").update({
                    "token_hash": token_hash,
                    "expires_at": expires_at
                }).eq("id", link_res.data[0]["id"]).execute()
            else:
                supabase_client.table("order_public_links").insert({
                    "order_id": order_id_str,
                    "shop_id": shop_id_val,
                    "token_hash": token_hash,
                    "expires_at": expires_at
                }).execute()
                
            base_url = getattr(settings, "FRONTEND_PUBLIC_BASE_URL", "http://localhost:3000")
            bill_url = f"{base_url}/bill/{raw_token}"
            total_amount = full_order.get("total_amount", 0)
            bill_msg = f"Your order has been delivered.\nTotal: ₹{total_amount}\nBill: {bill_url}"
            
            # Try to find destination
            channels = []
            if customer_id:
                channels_res = supabase_client.table("customer_channels").select("*").eq("customer_id", customer_id).execute()
                channels = channels_res.data if channels_res.data else []
                
            source = None
            card_phone = None
            telegram_chat_id = None
            action_card_id = full_order.get("action_card_id")
            
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
                elif full_order.get("customer_phone"): channel_to_use = "whatsapp"
                
            if channel_to_use == "telegram":
                chat_id = (telegram_channel.get("channel_chat_id") if telegram_channel else None) or telegram_chat_id
                if chat_id:
                    from app.services.telegram_service import telegram_service
                    telegram_service.send_message(chat_id, bill_msg)
                    notification_info["notification_sent"] = True
                    notification_info["notification_channel"] = "telegram"
                    print(f"DELIVERY_NOTIFICATION_SENT channel=telegram chat_id={chat_id}", flush=True)
                    logger.warning(f"DELIVERY_NOTIFICATION_SENT channel=telegram chat_id={chat_id}")
                else:
                    notification_info["notification_error"] = "No Telegram chat ID found"
                    print("DELIVERY_NOTIFICATION_SKIPPED reason=no_telegram_chat_id", flush=True)
                    logger.warning("DELIVERY_NOTIFICATION_SKIPPED reason=no_telegram_chat_id")
            elif channel_to_use == "whatsapp":
                phone_to_use = (whatsapp_channel.get("phone") if whatsapp_channel else None) or full_order.get("customer_phone") or card_phone
                if not phone_to_use and customer_id:
                    cust_res = supabase_client.table("customers").select("phone").eq("id", customer_id).execute()
                    if cust_res.data: phone_to_use = cust_res.data[0].get("phone")
                    
                if phone_to_use:
                    from app.services.twilio_whatsapp_service import twilio_whatsapp_service
                    result = twilio_whatsapp_service.send_whatsapp_message(phone_to_use, bill_msg)
                    notification_info["notification_sent"] = result.get("sent", False)
                    notification_info["notification_channel"] = "whatsapp"
                    notification_info["notification_sid"] = result.get("sid")
                    if result.get("error"):
                        notification_info["notification_error"] = result.get("error")
                        print(f"DELIVERY_NOTIFICATION_FAILED safe_error={result.get('error')}", flush=True)
                        logger.warning(f"DELIVERY_NOTIFICATION_FAILED safe_error={result.get('error')}")
                    else:
                        print(f"DELIVERY_NOTIFICATION_SENT channel=whatsapp sid={result.get('sid')}", flush=True)
                        logger.warning(f"DELIVERY_NOTIFICATION_SENT channel=whatsapp sid={result.get('sid')}")
                else:
                    notification_info["notification_error"] = "No customer phone found"
                    print("DELIVERY_NOTIFICATION_SKIPPED reason=no_whatsapp_phone", flush=True)
                    logger.warning("DELIVERY_NOTIFICATION_SKIPPED reason=no_whatsapp_phone")
            else:
                notification_info["notification_error"] = "No customer destination found"
                print("DELIVERY_NOTIFICATION_SKIPPED reason=no_customer_destination", flush=True)
                logger.warning("DELIVERY_NOTIFICATION_SKIPPED reason=no_customer_destination")
                
        except Exception as e:
            notification_info["notification_error"] = str(e)
            print(f"DELIVERY_NOTIFICATION_FAILED safe_error={str(e)}", flush=True)
            logger.warning(f"DELIVERY_NOTIFICATION_FAILED safe_error={str(e)}")

    final_res = supabase_client.table("orders").select("*, order_items(*)").eq("id", order_id).execute()
    final_data = final_res.data[0]
    if final_lifecycle_status == "delivered":
        final_data.update(notification_info)
        
    return final_data
