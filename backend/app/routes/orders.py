from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.dependencies.auth import get_current_user_id
from app.schemas.order import OrderResponse
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
