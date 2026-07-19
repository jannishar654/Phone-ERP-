from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

from app.schemas.business_config import BusinessType

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
    # Supabase owns credentials; this endpoint provisions business data only.
    shop_name: str = Field(default="Default Shop", min_length=1, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    business_type: BusinessType = BusinessType.grocery

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
    permissions: list[str] = Field(default_factory=list)
