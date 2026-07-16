import json
from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InboundChannel(str, Enum):
    WHATSAPP = "whatsapp"
    META_WHATSAPP = "meta_whatsapp"
    TELEGRAM = "telegram"


class InboundMessageType(str, Enum):
    TEXT = "text"
    VOICE = "voice"


class ConversationIntent(str, Enum):
    NEW_ORDER = "new_order"
    ORDER_UPDATE = "order_update"
    ORDER_CANCEL = "order_cancel"
    ORDER_TRACKING = "order_tracking"
    PRICE_ENQUIRY = "price_enquiry"
    PAYMENT_QUERY = "payment_query"
    BUSINESS_SUPPORT = "business_support"
    GENERAL_MESSAGE = "general_message"
    SPAM = "spam"
    UNCERTAIN = "uncertain"


class IntentClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: ConversationIntent = ConversationIntent.UNCERTAIN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    available: bool = True


class NormalizedInboundMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    shop_id: str = Field(min_length=1, max_length=128)
    customer_id: str = Field(min_length=1, max_length=128)
    channel: InboundChannel
    provider_message_id: str = Field(min_length=1, max_length=255)
    message_type: InboundMessageType
    raw_text: str = Field(min_length=1, max_length=20_000)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata_size(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        try:
            encoded = json.dumps(value, default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be JSON serializable") from exc
        if len(encoded.encode("utf-8")) > 16_384:
            raise ValueError("metadata exceeds 16 KB")
        return value
