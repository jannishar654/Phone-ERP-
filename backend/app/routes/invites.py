from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime, timedelta
import secrets
import hashlib
from app.dependencies.auth import get_current_user_id
from app.schemas.auth import StaffInviteCreate, StaffInviteResponse
from app.services.supabase import supabase_client
from app.routes.catalog import get_user_shop_id

router = APIRouter(prefix="/invites", tags=["Invites"])

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

@router.post("/staff", response_model=StaffInviteResponse)
def create_staff_invite(data: StaffInviteCreate, user_id: str = Depends(get_current_user_id)):
    # Re-use catalog's get_user_shop_id or use /me logic
    shop_id = get_user_shop_id(user_id)
    if shop_id != data.shop_id:
        raise HTTPException(status_code=403, detail="Forbidden: shop mismatch")
        
    raw_invite_code = secrets.token_urlsafe(16)
    invite_hash = hash_token(raw_invite_code)
    
    expires_at = None
    if data.expires_in_days:
        expires_at = (datetime.utcnow() + timedelta(days=data.expires_in_days)).isoformat()
        
    res = supabase_client.table("staff_invites").insert({
        "shop_id": shop_id,
        "role": data.role,
        "invite_code_hash": invite_hash,
        "label": data.label,
        "expires_at": expires_at,
        "created_by": user_id
    }).execute()
    
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create invite")
        
    created = res.data[0]
    return StaffInviteResponse(
        **created,
        raw_invite_code=raw_invite_code
    )

@router.get("/staff", response_model=List[StaffInviteResponse])
def list_staff_invites(user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    res = supabase_client.table("staff_invites").select("*").eq("shop_id", shop_id).is_("revoked_at", "null").is_("used_at", "null").execute()
    return [StaffInviteResponse(**row) for row in res.data] if res.data else []

@router.post("/staff/{invite_id}/revoke", response_model=StaffInviteResponse)
def revoke_staff_invite(invite_id: str, user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    now = datetime.utcnow().isoformat()
    res = supabase_client.table("staff_invites").update({"revoked_at": now}).eq("id", invite_id).eq("shop_id", shop_id).execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Invite not found or already revoked")
        
    return StaffInviteResponse(**res.data[0])
