from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class OperationType(str, Enum):
    ADD = "ADD"
    SET_QUANTITY = "SET_QUANTITY"
    CANCEL = "CANCEL"
    RETURN = "RETURN"
    SUBSTITUTE = "SUBSTITUTE"
    PREVIOUS_ORDER_REFERENCE = "PREVIOUS_ORDER_REFERENCE"

class OrderOperation(BaseModel):
    sequence: Optional[int] = None
    operation_id: Optional[str] = None
    target_operation_id: Optional[str] = None
    type: OperationType
    raw_product: Optional[str] = None
    quantity_raw: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    condition: Optional[str] = None
    evidence: str
    confidence: Optional[float] = None
