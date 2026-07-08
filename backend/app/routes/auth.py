from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies.auth import get_current_user_id
from app.services.supabase import supabase_client
from app.schemas.auth import RegisterStaffRequest, RegisterStaffResponse, MeResponse
import hashlib
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["Auth"])

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

@router.post("/register-staff", response_model=RegisterStaffResponse)
def register_staff(data: RegisterStaffRequest, user_id: str = Depends(get_current_user_id)):
    from app.config.settings import settings
    if not settings.REQUIRE_AUTH and not user_id:
        user_id = "mock-user"
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    # The user is already authenticated with Supabase. We just need to validate the invite.
    invite_hash = hash_token(data.invite_code)
    
    # Check invite
    res = supabase_client.table("staff_invites").select("*").eq("invite_code_hash", invite_hash).is_("used_at", "null").is_("revoked_at", "null").execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Invalid, expired, or used invite code")
        
    invite = res.data[0]
    
    if invite.get("expires_at"):
        expires_at = datetime.fromisoformat(invite["expires_at"].replace('Z', '+00:00'))
        if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
            raise HTTPException(status_code=400, detail="Invite code has expired")
            
    shop_id = invite["shop_id"]
    role = invite["role"]
    
    # Check if user is already a member
    mem_res = supabase_client.table("shop_members").select("id").eq("user_id", user_id).eq("shop_id", shop_id).eq("status", "active").execute()
    if mem_res.data:
        raise HTTPException(status_code=400, detail="User is already a member of this shop")
        
    # Create shop_members row
    mem_insert = supabase_client.table("shop_members").insert({
        "shop_id": shop_id,
        "user_id": user_id,
        "role": role,
        "created_by": user_id
    }).execute()
    
    if not mem_insert.data:
        raise HTTPException(status_code=500, detail="Failed to create shop membership")
        
    # Mark invite as used
    now = datetime.utcnow().isoformat()
    supabase_client.table("staff_invites").update({"used_at": now}).eq("id", invite["id"]).execute()
    
    return RegisterStaffResponse(
        success=True,
        shop_id=shop_id,
        role=role
    )

@router.get("/me", response_model=MeResponse)
def get_me(user_id: str = Depends(get_current_user_id)):
    from app.config.settings import settings
    if not settings.REQUIRE_AUTH and not user_id:
        user_id = "mock-user"
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

        
    # Check shop_members first
    mem_res = supabase_client.table("shop_members").select("*").eq("user_id", user_id).eq("status", "active").execute()
    
    if mem_res.data:
        member = mem_res.data[0]
        return MeResponse(
            user_id=user_id,
            shop_id=member["shop_id"],
            role=member["role"],
            permissions=[member["role"]]
        )
        
    # Fallback to shops.owner_id
    shop_res = supabase_client.table("shops").select("id").eq("owner_id", user_id).execute()
    if shop_res.data:
        return MeResponse(
            user_id=user_id,
            shop_id=shop_res.data[0]["id"],
            role="owner",
            permissions=["owner"]
        )
        
    # If not found anywhere, user exists but has no shop/role
    return MeResponse(user_id=user_id, role="none")
