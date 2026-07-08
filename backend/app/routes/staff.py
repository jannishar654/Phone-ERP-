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
    token: str

@router.post("/orders/packing", response_model=List[OrderResponse])
def get_packing_orders(req: StaffOrderRequest):
    access = get_staff_access_by_token(req.token)
    if not access or access["role"] not in ["owner", "packer"]:
        raise HTTPException(status_code=403, detail="Invalid token or insufficient permissions")
        
    res = supabase_client.table("orders").select("*, order_items(*)").eq("shop_id", access["shop_id"]).eq("lifecycle_status", "packing").order("created_at", desc=False).execute()
    return res.data if res.data else []

@router.post("/orders/delivery", response_model=List[OrderResponse])
def get_delivery_orders(req: StaffOrderRequest):
    access = get_staff_access_by_token(req.token)
    if not access or access["role"] not in ["owner", "delivery"]:
        raise HTTPException(status_code=403, detail="Invalid token or insufficient permissions")
        
    res = supabase_client.table("orders").select("*, order_items(*)").eq("shop_id", access["shop_id"]).eq("lifecycle_status", "out_for_delivery").order("created_at", desc=False).execute()
    return res.data if res.data else []

class UpdateLifecycleStatusStaff(BaseModel):
    token: str
    lifecycle_status: str

@router.post("/orders/{order_id}/status", response_model=OrderResponse)
def staff_update_order_status(order_id: str, data: UpdateLifecycleStatusStaff):
    access = get_staff_access_by_token(data.token)
    if not access:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    new_status = data.lifecycle_status
    role = access["role"]
    
    # Packer can only move to out_for_delivery
    if role == "packer" and new_status != "out_for_delivery":
        raise HTTPException(status_code=403, detail="Packers can only mark orders as out_for_delivery")
        
    # Delivery can only move to delivered or cancelled
    if role == "delivery" and new_status not in ["delivered", "cancelled"]:
        raise HTTPException(status_code=403, detail="Delivery staff can only mark orders as delivered or cancelled")
        
    res = supabase_client.table("orders").select("*").eq("id", order_id).eq("shop_id", access["shop_id"]).execute()
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
    if new_status == "delivered":
        try:
            order_id_str = str(order_id)
            customer_id = order.get("customer_id")
            if customer_id:
                # Find customer channels
                channels_res = supabase_client.table("customer_channels").select("*").eq("customer_id", customer_id).execute()
                channels = channels_res.data if channels_res.data else []
                
                # Check for public bill link
                bill_msg = ""
                
                import secrets
                from datetime import timedelta
                raw_token = secrets.token_urlsafe(32)
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
                        "shop_id": access["shop_id"],
                        "token_hash": token_hash,
                        "expires_at": expires_at
                    }).execute()
                
                bill_url = f"http://localhost:3000/bill/{raw_token}" # In production, use env var
                bill_msg = f"\nView your bill & status: {bill_url}"
                
                for channel in channels:
                    if channel["channel"] == "telegram" and channel.get("channel_chat_id"):
                        from app.services.telegram_service import telegram_service
                        telegram_service.send_message(
                            channel["channel_chat_id"], 
                            f"Your order #{order.get('order_number', '...')} has been delivered!{bill_msg}"
                        )
                    # Add WhatsApp if needed
        except Exception as e:
            print(f"Warning: Failed to send notification: {e}")
            
    final_res = supabase_client.table("orders").select("*, order_items(*)").eq("id", order_id).execute()
    return final_res.data[0]
