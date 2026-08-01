from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BusinessType(str, Enum):
    grocery = "grocery"
    wholesale = "wholesale"
    restaurant = "restaurant"
    pharmacy = "pharmacy"
    bakery = "bakery"
    hardware = "hardware"
    general = "general"


class BusinessConfigurationBase(BaseModel):
    business_type: BusinessType = BusinessType.grocery
    display_name: Optional[str] = Field(default=None, max_length=120)
    required_order_fields: List[str] = Field(default_factory=list, max_length=30)
    optional_order_fields: List[str] = Field(default_factory=list, max_length=30)
    workflow_stages: List[str] = Field(default_factory=list, max_length=20)
    extraction_context: Dict[str, Any] = Field(default_factory=dict)
    terminology: Dict[str, str] = Field(default_factory=dict)
    settings: Dict[str, Any] = Field(default_factory=dict)
    active: bool = True

    @field_validator(
        "required_order_fields", "optional_order_fields", "workflow_stages"
    )
    @classmethod
    def validate_identifiers(cls, values: List[str]) -> List[str]:
        cleaned = [str(value).strip() for value in values]
        if any(not value or len(value) > 64 for value in cleaned):
            raise ValueError("Configuration identifiers must be 1-64 characters")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Configuration identifiers must be unique")
        return cleaned

    @field_validator("terminology")
    @classmethod
    def validate_terminology(cls, value: Dict[str, str]) -> Dict[str, str]:
        if len(value) > 30:
            raise ValueError("Too many terminology entries")
        return {
            str(key)[:64]: str(label)[:120]
            for key, label in value.items()
            if str(key).strip() and str(label).strip()
        }


class BusinessConfigurationCreate(BusinessConfigurationBase):
    shop_id: str


class BusinessConfiguration(BusinessConfigurationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    shop_id: str
    created_at: datetime
    updated_at: datetime
