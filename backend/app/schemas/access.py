from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class StaffAccessCreate(BaseModel):
    shop_id: str
    role: str
    label: Optional[str] = None
    expires_in_days: Optional[int] = 7

class StaffAccessResponse(BaseModel):
    id: str
    shop_id: str
    role: str
    label: Optional[str] = None
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime
    # We don't return token_hash in response usually, but we will return raw token just once on creation
    raw_token: Optional[str] = None

class StaffAccessValidateRequest(BaseModel):
    token: str

class StaffAccessValidateResponse(BaseModel):
    valid: bool
    shop_id: Optional[str] = None
    role: Optional[str] = None
    expires_at: Optional[datetime] = None

class OrderPublicLinkCreate(BaseModel):
    order_id: str
    shop_id: str
    expires_in_days: Optional[int] = 30

class OrderPublicLinkResponse(BaseModel):
    id: str
    order_id: str
    shop_id: str
    expires_at: Optional[datetime]
    created_at: datetime
    raw_token: Optional[str] = None

class OrderPublicLinkValidateRequest(BaseModel):
    token: str

class DeliveryCreate(BaseModel):
    shop_id: str
    order_id: str
    assigned_to_name: Optional[str] = None
    assigned_to_phone: Optional[str] = None

class DeliveryResponse(DeliveryCreate):
    id: str
    status: Optional[str] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
