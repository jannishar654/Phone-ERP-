from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
import re

def normalize_indian_phone(v: Optional[str]) -> Optional[str]:
    if not v:
        return v
    # Remove all non-digit characters except '+'
    cleaned = re.sub(r'[^\d+]', '', str(v))
    if not cleaned:
        return v
    # If it's exactly 10 digits, assume Indian and prepend +91
    if re.fullmatch(r'\d{10}', cleaned):
        return f"+91{cleaned}"
    # If it starts with 91 and has 12 digits total
    if re.fullmatch(r'91\d{10}', cleaned):
        return f"+{cleaned}"
    return cleaned

class Item(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = ""
    price: Optional[float] = Field(None, ge=0.0)
    pack_size: Optional[str] = None
    price_status: Optional[str] = None
    confidence: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)
    raw_name: Optional[str] = None
    canonical_name: Optional[str] = None
    resolution_status: Optional[str] = None
    resolution_source: Optional[str] = None
    possible_matches: List[str] = Field(default_factory=list)
    resolution_confidence: Optional[float] = None
    alias_used: Optional[bool] = False


class ActionCard(BaseModel):
    id: str
    user_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

    @validator("customer_phone", pre=True)
    def normalize_phone(cls, v):
        return normalize_indian_phone(v)
    items: List[Item] = Field(default_factory=list)
    delivery_address: Optional[str] = None
    delivery_time: Optional[str] = None
    delivery_time_raw: Optional[str] = None
    delivery_time_normalized: Optional[str] = None
    delivery_time_confidence: Optional[float] = None
    delivery_time_warning: Optional[str] = None
    delivery_address_raw: Optional[str] = None
    risk_flags: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    payment_method: Optional[str] = None
    status: str = "pending"
    source: str
    message_type: str = "ORDER"
    confidence: Optional[float] = None
    confidence_score: Optional[int] = None
    confidence_label: Optional[str] = None
    confidence_reasons: Optional[List[str]] = Field(default_factory=list)
    stt_provider: Optional[str] = None
    extraction_provider: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    transcript: str
    order_id: Optional[str] = None
    shop_id: Optional[str] = None
    customer_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ActionCardCreate(BaseModel):
    user_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

    @validator("customer_phone", pre=True)
    def normalize_phone(cls, v):
        return normalize_indian_phone(v)
    items: List[Item] = Field(default_factory=list)
    delivery_address: Optional[str] = None
    delivery_time: Optional[str] = None
    delivery_time_raw: Optional[str] = None
    delivery_time_normalized: Optional[str] = None
    delivery_time_confidence: Optional[float] = None
    delivery_time_warning: Optional[str] = None
    delivery_address_raw: Optional[str] = None
    risk_flags: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    validation_warnings: List[str] = Field(default_factory=list)
    status: str = "pending"
    source: str = "text"
    message_type: str = "ORDER"
    confidence: Optional[float] = None
    confidence_score: Optional[int] = None
    confidence_label: Optional[str] = None
    confidence_reasons: Optional[List[str]] = Field(default_factory=list)
    stt_provider: Optional[str] = None
    extraction_provider: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    transcript: str = "Manual order entry"
    shop_id: Optional[str] = None
    customer_id: Optional[str] = None


class ActionCardUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

    @validator("customer_phone", pre=True)
    def normalize_phone(cls, v):
        return normalize_indian_phone(v)
    items: Optional[List[Item]] = None
    delivery_address: Optional[str] = None
    delivery_time: Optional[str] = None
    delivery_time_raw: Optional[str] = None
    delivery_time_normalized: Optional[str] = None
    delivery_time_confidence: Optional[float] = None
    delivery_time_warning: Optional[str] = None
    delivery_address_raw: Optional[str] = None
    risk_flags: Optional[List[str]] = None
    missing_fields: Optional[List[str]] = None
    validation_warnings: Optional[List[str]] = None
    status: Optional[str] = None
    source: Optional[str] = None
    message_type: Optional[str] = None
    confidence: Optional[float] = None
    confidence_score: Optional[int] = None
    confidence_label: Optional[str] = None
    confidence_reasons: Optional[List[str]] = None
    stt_provider: Optional[str] = None
    extraction_provider: Optional[str] = None
    metadata: Optional[dict] = None
    transcript: Optional[str] = None
    order_id: Optional[str] = None
    shop_id: Optional[str] = None
    customer_id: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str
