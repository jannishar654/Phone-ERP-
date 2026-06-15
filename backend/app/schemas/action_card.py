from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Item(BaseModel):
    name: str
    quantity: int = Field(..., ge=1)
    unit: Optional[str] = ""
    price: Optional[float] = Field(None, ge=0.0)


class ActionCard(BaseModel):
    id: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    items: List[Item] = Field(default_factory=list)
    delivery_address: Optional[str] = None
    delivery_time: Optional[str] = None
    status: str = "pending"
    source: str
    transcript: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ActionCardCreate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    items: List[Item] = Field(default_factory=list)
    delivery_address: Optional[str] = None
    delivery_time: Optional[str] = None
    status: str = "pending"
    source: str = "text"
    transcript: str = "Manual order entry"


class ActionCardUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    items: Optional[List[Item]] = None
    delivery_address: Optional[str] = None
    delivery_time: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    transcript: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str
