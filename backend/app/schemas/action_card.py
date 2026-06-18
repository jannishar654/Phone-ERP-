from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Item(BaseModel):
    name: str
    quantity: float = Field(..., gt=0)
    unit: Optional[str] = ""
    price: Optional[float] = Field(None, ge=0.0)
    pack_size: Optional[str] = None
    price_status: Optional[str] = None
    confidence: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)


class ActionCard(BaseModel):
    id: str
    user_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
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
    stt_provider: Optional[str] = None
    extraction_provider: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    transcript: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ActionCardCreate(BaseModel):
    user_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
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
    stt_provider: Optional[str] = None
    extraction_provider: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    transcript: str = "Manual order entry"


class ActionCardUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
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
    stt_provider: Optional[str] = None
    extraction_provider: Optional[str] = None
    metadata: Optional[dict] = None
    transcript: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str
