from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import hashlib
from datetime import datetime
from typing import List, Optional
from app.services.supabase import supabase_client

router = APIRouter(prefix="/public", tags=["Public"])

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

class PublicBillItem(BaseModel):
    id: str
    display_name: Optional[str] = None
    raw_name: str
    quantity: float
    unit: Optional[str] = None
    unit_price: float = 0.0
    line_total: float = 0.0

class PublicBillResponse(BaseModel):
    shop_name: str
    order_id: str
    order_number: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_time: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    payment_method: Optional[str] = None
    total_amount: float = 0.0
    lifecycle_status: Optional[str] = None
    items: List[PublicBillItem]

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
    
    order_res = (
        supabase_client.table("orders")
        .select("*, order_items(*)")
        .eq("id", order_id)
        .eq("shop_id", shop_id)
        .execute()
    )
    if not order_res.data:
        raise HTTPException(status_code=404, detail="Order not found")
        
    shop_res = supabase_client.table("shops").select("id, name, owner_id").eq("id", shop_id).execute()
    shop_info = shop_res.data[0] if shop_res.data else {}
    
    order_data = order_res.data[0]
    
    customer_name = order_data.get("customer_name")
    customer_phone = order_data.get("customer_phone")
    
    if not customer_name or not customer_phone:
        if order_data.get("customer_id"):
            cust_res = supabase_client.table("customers").select("name, phone").eq("id", order_data["customer_id"]).execute()
            if cust_res.data:
                customer_name = customer_name or cust_res.data[0].get("name")
                customer_phone = customer_phone or cust_res.data[0].get("phone")
                
        if (not customer_name or not customer_phone) and order_data.get("action_card_id"):
            ac_res = supabase_client.table("action_cards").select("customer_name, customer_phone").eq("id", order_data["action_card_id"]).execute()
            if ac_res.data:
                customer_name = customer_name or ac_res.data[0].get("customer_name")
                customer_phone = customer_phone or ac_res.data[0].get("customer_phone")
    
    return PublicBillResponse(
        shop_name=shop_info.get("name", "Store"),
        order_id=order_data["id"],
        order_number=order_data.get("orderNumber") or order_data.get("order_number"),
        customer_name=customer_name,
        customer_phone=customer_phone,
        delivery_address=order_data.get("delivery_address"),
        delivery_time=order_data.get("delivery_time"),
        delivered_at=order_data.get("delivered_at"),
        payment_method=order_data.get("payment_method"),
        total_amount=order_data.get("total_amount", 0.0),
        lifecycle_status=order_data.get("lifecycle_status"),
        items=order_data.get("order_items", [])
    )
