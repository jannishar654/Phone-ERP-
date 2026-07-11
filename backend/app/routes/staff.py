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
    
    # Send notification if delivered and transitioning to it
    notification_info = {}
    print(f"STAFF_STATUS_DELIVERED_BRANCH_CHECK new_status={final_lifecycle_status} is_delivered={final_lifecycle_status == 'delivered'}", flush=True)
    logger.warning(f"STAFF_STATUS_DELIVERED_BRANCH_CHECK new_status={final_lifecycle_status} is_delivered={final_lifecycle_status == 'delivered'}")
    
    # We only send if transitioning TO delivered
    if final_lifecycle_status == "delivered" and current_status != "delivered":
        from app.services.delivery_notification_service import send_delivery_notification
        notification_info = send_delivery_notification(order_id, final_order)

    final_res = supabase_client.table("orders").select("*, order_items(*)").eq("id", order_id).execute()
    final_data = final_res.data[0]
    if final_lifecycle_status == "delivered" and notification_info:
        final_data.update(notification_info)
        
    return final_data
