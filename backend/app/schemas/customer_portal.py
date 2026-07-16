from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MagicLinkExchange(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class CustomerPortalSessionResponse(BaseModel):
    session_token: str
    expires_at: datetime
    customer_name: str
    shop_name: str


class CustomerPortalItem(BaseModel):
    id: str
    display_name: Optional[str] = None
    raw_name: str
    quantity: float
    unit: Optional[str] = None
    unit_price: float = 0.0
    line_total: float = 0.0


class CustomerPortalEvent(BaseModel):
    lifecycle_status: str
    occurred_at: datetime


class CustomerPortalOrder(BaseModel):
    id: str
    record_type: Literal["order", "action_card"] = "order"
    order_number: Optional[int] = None
    total_amount: float = 0.0
    lifecycle_status: str
    delivery_address: Optional[str] = None
    delivery_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    packed_at: Optional[datetime] = None
    out_for_delivery_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    items: List[CustomerPortalItem] = Field(default_factory=list)
    events: List[CustomerPortalEvent] = Field(default_factory=list)


class CustomerPortalOverview(BaseModel):
    customer_name: str
    shop_name: str
    orders: List[CustomerPortalOrder]


CustomerRequestType = Literal[
    "repeat_order", "cancel_order", "change_order", "support"
]


class CustomerRequestCreate(BaseModel):
    request_type: CustomerRequestType
    message: Optional[str] = Field(default=None, max_length=2000)
    payload: Dict[str, Any] = Field(default_factory=dict)


class CustomerAssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class CustomerAssistantResponse(BaseModel):
    reply: str
    intent: str
    order_id: Optional[str] = None
    action: Optional[str] = None
