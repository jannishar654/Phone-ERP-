from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class StaffInviteCreate(BaseModel):
    shop_id: str
    role: str
    label: Optional[str] = None
    expires_in_days: Optional[int] = 7

class StaffInviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    shop_id: str
    role: str
    label: Optional[str] = None
    expires_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime
    raw_invite_code: Optional[str] = None  # Only returned on creation

class RegisterOwnerRequest(BaseModel):
    # Supabase handles the actual email/pwd signup, 
    # this endpoint just sets up the shop if needed.
    # Actually, owner registration might just use existing logic or be handled mostly by frontend,
    # but we'll include it for completeness if the frontend calls it after signup.
    shop_name: str
    phone: str

class RegisterStaffRequest(BaseModel):
    invite_code: str
    
class RegisterStaffResponse(BaseModel):
    success: bool
    shop_id: str
    role: str

class MeResponse(BaseModel):
    user_id: str
    shop_id: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    permissions: list[str] = []
