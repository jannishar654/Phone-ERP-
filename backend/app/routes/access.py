from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime, timedelta
import secrets
import hashlib
from app.dependencies.auth import get_current_user_id
from app.schemas.access import StaffAccessCreate, StaffAccessResponse, OrderPublicLinkCreate, OrderPublicLinkResponse
from app.services.supabase import supabase_client
from app.routes.catalog import get_user_shop_id

router = APIRouter(prefix="/access", tags=["Access"])

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

@router.post("/staff", response_model=StaffAccessResponse)
def create_staff_access(data: StaffAccessCreate, user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    if shop_id != data.shop_id:
        raise HTTPException(status_code=403, detail="Forbidden: shop mismatch")
        
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    
    expires_at = None
    if data.expires_in_days:
        expires_at = (datetime.utcnow() + timedelta(days=data.expires_in_days)).isoformat()
        
    res = supabase_client.table("shop_staff_access").insert({
        "shop_id": shop_id,
        "role": data.role,
        "token_hash": token_hash,
        "label": data.label,
        "expires_at": expires_at,
        "created_by": user_id
    }).execute()
    
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create staff access")
        
    created = res.data[0]
    return StaffAccessResponse(
        **created,
        raw_token=raw_token
    )

@router.get("/staff", response_model=List[StaffAccessResponse])
def list_staff_access(user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    res = supabase_client.table("shop_staff_access").select("*").eq("shop_id", shop_id).is_("revoked_at", "null").execute()
    return [StaffAccessResponse(**row) for row in res.data] if res.data else []

@router.post("/staff/{access_id}/revoke", response_model=StaffAccessResponse)
def revoke_staff_access(access_id: str, user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    now = datetime.utcnow().isoformat()
    res = supabase_client.table("shop_staff_access").update({"revoked_at": now}).eq("id", access_id).eq("shop_id", shop_id).execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Access token not found or already revoked")
        
    return StaffAccessResponse(**res.data[0])

@router.post("/customer/{order_id}", response_model=OrderPublicLinkResponse)
def create_customer_link(order_id: str, data: OrderPublicLinkCreate, user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    if shop_id != data.shop_id:
        raise HTTPException(status_code=403, detail="Forbidden: shop mismatch")
        
    # Check if order exists
    order_res = supabase_client.table("orders").select("id").eq("id", order_id).eq("shop_id", shop_id).execute()
    if not order_res.data:
        raise HTTPException(status_code=404, detail="Order not found")
        
    # Check if there is already an active link, if so just return it (although without raw token since we don't store it)
    # Wait, for customer links, maybe we just generate a new one
    
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    
    expires_at = None
    if data.expires_in_days:
        expires_at = (datetime.utcnow() + timedelta(days=data.expires_in_days)).isoformat()
        
    res = supabase_client.table("order_public_links").insert({
        "order_id": order_id,
        "shop_id": shop_id,
        "token_hash": token_hash,
        "expires_at": expires_at
    }).execute()
    
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create customer link")
        
    created = res.data[0]
    return OrderPublicLinkResponse(
        **created,
        raw_token=raw_token
    )
