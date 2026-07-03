from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime
from app.dependencies.auth import get_current_user_id
from app.schemas.order import OrderResponse, OrderLifecycleUpdate
from app.services.order_service import order_service
from app.services.supabase import supabase_client

router = APIRouter(prefix="/orders", tags=["Orders"])

from app.routes.catalog import get_user_shop_id

@router.post("/action-cards/{action_card_id}/convert", response_model=OrderResponse)
def convert_action_card(action_card_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        order = order_service.convert_action_card_to_order(action_card_id, user_id)
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[OrderResponse])
def get_orders(user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    res = supabase_client.table("orders").select("*, order_items(*)").eq("shop_id", shop_id).order("created_at", desc=True).execute()
    return res.data if res.data else []

@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(order_id: str, update_data: OrderLifecycleUpdate, user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    
    res = supabase_client.table("orders").select("*").eq("id", order_id).eq("shop_id", shop_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order = res.data[0]
    current_status = order.get("lifecycle_status")
    new_status = update_data.lifecycle_status
    
    valid_transitions = {
        None: ["pending_review", "packing", "cancelled"],
        "pending_review": ["packing", "cancelled"],
        "packing": ["out_for_delivery", "cancelled"],
        "out_for_delivery": ["delivered", "cancelled"],
        "delivered": [],
        "cancelled": []
    }
    
    allowed = valid_transitions.get(current_status, [])
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid transition from {current_status} to {new_status}")
        
    updates = {"lifecycle_status": new_status}
    now_iso = datetime.utcnow().isoformat()
    if new_status == "packing":
        updates["packed_at"] = now_iso
    elif new_status == "out_for_delivery":
        updates["out_for_delivery_at"] = now_iso
    elif new_status == "delivered":
        updates["delivered_at"] = now_iso
    elif new_status == "cancelled":
        updates["cancelled_at"] = now_iso
        
    update_res = supabase_client.table("orders").update(updates).eq("id", order_id).execute()
    if not update_res.data:
        raise HTTPException(status_code=500, detail="Failed to update order")
        
    final_res = supabase_client.table("orders").select("*, order_items(*)").eq("id", order_id).execute()
    return final_res.data[0]
