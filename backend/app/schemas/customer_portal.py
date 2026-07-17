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
    source_id: str
    record_type: Literal["order", "action_card"] = "order"
    display_reference: str
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
    revision: int = 1
    can_edit: bool = False
    can_request_change: bool = False
    can_request_cancellation: bool = False
    restriction_reason: Optional[str] = None
    items: List[CustomerPortalItem] = Field(default_factory=list)
    events: List[CustomerPortalEvent] = Field(default_factory=list)


class CustomerPortalOverview(BaseModel):
    customer_name: str
    shop_name: str
    orders: List[CustomerPortalOrder]


CustomerRequestType = Literal[
    "repeat_order", "cancel_order", "change_order", "support"
]


class CustomerAmendmentItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0, le=100000)
    unit: Optional[str] = Field(default=None, max_length=50)


class CustomerOrderAmendment(BaseModel):
    items: List[CustomerAmendmentItem] = Field(min_length=1, max_length=100)
    delivery_address: Optional[str] = Field(default=None, max_length=500)
    delivery_time: Optional[str] = Field(default=None, max_length=200)


class CustomerDraftUpdate(CustomerOrderAmendment):
    expected_revision: int = Field(ge=1)


class CustomerRequestCreate(BaseModel):
    request_type: CustomerRequestType
    message: Optional[str] = Field(default=None, max_length=2000)
    payload: Dict[str, Any] = Field(default_factory=dict)
    amendment: Optional[CustomerOrderAmendment] = None


class CustomerAssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class CustomerAssistantResponse(BaseModel):
    reply: str
    intent: str
    order_id: Optional[str] = None
    action: Optional[str] = None
