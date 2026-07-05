from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class OrderItemBase(BaseModel):
    catalog_item_id: Optional[str] = None
    raw_name: str
    quantity: float
    unit: Optional[str] = None
    unit_price: float = Field(default=0.0, ge=0.0)
    line_total: float = Field(default=0.0, ge=0.0)

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemResponse(OrderItemBase):
    id: str
    order_id: str
    created_at: datetime

    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    shop_id: str
    customer_id: Optional[str] = None
    action_card_id: Optional[str] = None
    total_amount: float = Field(default=0.0, ge=0.0)
    status: str = "pending"
    lifecycle_status: Optional[str] = None
    delivery_address: Optional[str] = None
    delivery_time: Optional[datetime] = None
    payment_method: Optional[str] = None
    packed_at: Optional[datetime] = None
    out_for_delivery_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    orderNumber: Optional[int] = Field(None, validation_alias="order_number", serialization_alias="orderNumber")

class OrderCreate(OrderBase):
    items: List[OrderItemCreate]

class OrderResponse(OrderBase):
    id: str
    created_at: datetime
    updated_at: datetime
    order_items: List[OrderItemResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True

class OrderLifecycleUpdate(BaseModel):
    lifecycle_status: str
