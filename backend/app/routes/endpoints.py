from fastapi import APIRouter, UploadFile, File, HTTPException, status
from typing import List, Dict, Any
from app.schemas.action_card import ActionCard, Item, ActionCardCreate, ActionCardUpdate, StatusUpdate
from app.controllers.action_card import ActionCardController
from pydantic import BaseModel
from datetime import datetime
from app.services.gemini import GeminiService
from google.genai import errors

router = APIRouter()

class ExtractRequest(BaseModel):
    transcript: str
    source: str = "text"

# Health check endpoint
@router.get("/health", status_code=status.HTTP_200_OK, response_model=Dict[str, str])
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "PhoneERP Backend"
    }

# Mock audio transcription endpoint
@router.post("/transcribe", status_code=status.HTTP_200_OK)
async def transcribe_audio(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio filename is required.",
        )

    supported_formats = (".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".webm")

    if not file.filename.lower().endswith(supported_formats):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio format. Supported: WAV, MP3, M4A, MP4, OGG, WEBM.",
        )

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty.",
        )

    try:
        transcript = await GeminiService.transcribe_audio_file(
            file_content=file_content,
            filename=file.filename,
        )
    except Exception as error:
        err_msg = str(error).upper()
        is_quota = False
        if isinstance(error, errors.APIError) and (error.code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "QUOTA" in err_msg):
            is_quota = True
        elif "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "QUOTA" in err_msg:
            is_quota = True

        if is_quota:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Voice processing is temporarily unavailable due to API quota limits. Please enter the order manually.",
            ) from error

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    return {
        "filename": file.filename,
        "transcript": transcript,
        "confidence": None,
        "message": "Audio transcribed successfully.",
    }
# Entity extraction endpoint
@router.post("/extract-action-card", response_model=ActionCard, status_code=status.HTTP_201_CREATED)
async def extract_action_card(payload: ExtractRequest) -> ActionCard:
    try:
        extracted = await GeminiService.extract_order_details(payload.transcript)
        print(f"Extracted data: {extracted}")
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    # Sanitize items to ensure types/constraints (Pydantic will enforce quantity > 0)
    raw_items = extracted.get("items", []) or []
    safe_items = []
    for it in raw_items:
        try:
            name = (it.get("name") or "").strip() if isinstance(it, dict) else str(it)
            if not name:
                name = "Unknown Item"

            # Preserve decimal quantities such as 2.5 kg.
            qty = 1.0
            if isinstance(it, dict) and it.get("quantity") is not None:
                try:
                    qty = float(it.get("quantity") or 0)
                except Exception:
                    qty = 1.0
            if qty <= 0:
                qty = 1.0

            unit = (it.get("unit") or "") if isinstance(it, dict) else ""
            price = None
            if isinstance(it, dict) and it.get("price") is not None:
                try:
                    price = float(it.get("price"))
                except Exception:
                    price = None

            safe_items.append({"name": name, "quantity": qty, "unit": unit, "price": price})
        except Exception:
            # On any unexpected structure, fall back to a single unknown item
            safe_items.append({"name": "Unknown Item", "quantity": 1, "unit": "", "price": None})

    # Create Pydantic Item models (this will still validate and raise if something unexpected remains)
    try:
        items_models = [Item(**item) for item in safe_items]
    except Exception:
        # If validation still fails, fallback to a minimal item list
        items_models = [Item(name="Unknown Item", quantity=1, price=None)]

    card_data = {
        "customer_name": extracted.get("customer_name", "Unknown"),
        "customer_phone": extracted.get("customer_phone", ""),
        "items": items_models,
        "delivery_address": extracted.get("delivery_address", ""),
        "delivery_time": extracted.get("delivery_time", ""),
        "status": "pending",
        "source": payload.source,
        "transcript": payload.transcript,
    }

    return ActionCardController.create_card(card_data)

# Get all orders/cards
@router.get("/action-cards", response_model=List[ActionCard], status_code=status.HTTP_200_OK)
async def get_action_cards() -> List[ActionCard]:
    return ActionCardController.get_all_cards()

# Get card by ID
@router.get("/action-cards/{card_id}", response_model=ActionCard, status_code=status.HTTP_200_OK)
async def get_action_card(card_id: str) -> ActionCard:
    card = ActionCardController.get_card_by_id(card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ActionCard with ID {card_id} not found"
        )
    return card

# Create manual card
@router.post("/action-cards", response_model=ActionCard, status_code=status.HTTP_201_CREATED)
async def create_action_card(payload: ActionCardCreate) -> ActionCard:
    return ActionCardController.create_card(payload.model_dump())

# Edit card
@router.put("/action-cards/{card_id}", response_model=ActionCard, status_code=status.HTTP_200_OK)
async def update_action_card(card_id: str, payload: ActionCardUpdate) -> ActionCard:
    updated_card = ActionCardController.update_card(card_id, payload.model_dump(exclude_unset=True))
    if not updated_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ActionCard with ID {card_id} not found"
        )
    return updated_card

# Quick status update
@router.patch("/action-cards/{card_id}/status", response_model=ActionCard, status_code=status.HTTP_200_OK)
async def update_action_card_status(card_id: str, payload: StatusUpdate) -> ActionCard:
    updated_card = ActionCardController.update_card_status(card_id, payload.status)
    if not updated_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ActionCard with ID {card_id} not found"
        )
    return updated_card

# Delete card
@router.delete("/action-cards/{card_id}", status_code=status.HTTP_200_OK)
async def delete_action_card(card_id: str):
    success = ActionCardController.delete_card(card_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ActionCard with ID {card_id} not found"
        )
    return {"message": f"ActionCard {card_id} deleted successfully"}
