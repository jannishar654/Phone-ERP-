from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import hashlib
from datetime import datetime
from app.schemas.order import OrderResponse
from app.services.supabase import supabase_client

router = APIRouter(prefix="/public", tags=["Public"])

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

class PublicBillResponse(BaseModel):
    order: OrderResponse
    shop_info: dict

@router.get("/bill/{token}", response_model=PublicBillResponse)
def get_customer_bill(token: str):
    token_hash = hash_token(token)
    res = supabase_client.table("order_public_links").select("*").eq("token_hash", token_hash).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Invalid bill link")
        
    link = res.data[0]
    
    if link.get("expires_at"):
        expires_at = datetime.fromisoformat(link["expires_at"].replace('Z', '+00:00'))
        if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
            raise HTTPException(status_code=410, detail="Bill link expired")
            
    order_id = link["order_id"]
    shop_id = link["shop_id"]
    
    order_res = supabase_client.table("orders").select("*, order_items(*)").eq("id", order_id).execute()
    if not order_res.data:
        raise HTTPException(status_code=404, detail="Order not found")
        
    shop_res = supabase_client.table("shops").select("id, name, owner_id").eq("id", shop_id).execute()
    shop_info = shop_res.data[0] if shop_res.data else {}
    
    return PublicBillResponse(
        order=order_res.data[0],
        shop_info=shop_info
    )
