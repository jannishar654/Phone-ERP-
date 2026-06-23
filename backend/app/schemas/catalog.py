from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class CatalogItemBase(BaseModel):
    canonical_name: str
    display_name: str
    english_name: Optional[str] = None
    base_price: float = Field(default=0.0, ge=0.0)
    unit: Optional[str] = None
    category: Optional[str] = None
    active: bool = True
    in_stock: bool = True

class CatalogItemCreate(CatalogItemBase):
    shop_id: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)

class CatalogItemUpdate(BaseModel):
    canonical_name: Optional[str] = None
    display_name: Optional[str] = None
    english_name: Optional[str] = None
    base_price: Optional[float] = Field(None, ge=0.0)
    unit: Optional[str] = None
    category: Optional[str] = None
    active: Optional[bool] = None
    in_stock: Optional[bool] = None
    aliases: Optional[List[str]] = None

class CatalogItemResponse(CatalogItemBase):
    id: str
    shop_id: str
    created_at: datetime
    updated_at: datetime
    aliases: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True
