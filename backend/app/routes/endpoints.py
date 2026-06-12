from fastapi import APIRouter, UploadFile, File, HTTPException, status
from typing import List, Dict, Any
from app.schemas.action_card import ActionCard, Item, ActionCardCreate, ActionCardUpdate, StatusUpdate
from app.controllers.action_card import ActionCardController
from pydantic import BaseModel
from datetime import datetime

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
    if not file.filename.lower().endswith(('.wav', '.mp3', '.m4a', '.ogg', '.webm')):
     raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported audio format. Supported: .wav, .mp3, .m4a, .ogg, .webm"
    )
    
    return {
        "filename": file.filename,
        "transcript": "Order five dilithium crystals for Captain Janeway, deliver to Voyager Cargo Bay 1 ASAP.",
        "confidence": 0.98,
        "duration_seconds": 8.4,
        "message": "Audio file uploaded successfully. Transcription is a placeholder."
    }

# Mock entity extraction endpoint
@router.post("/extract-action-card", response_model=ActionCard, status_code=status.HTTP_201_CREATED)
async def extract_action_card(payload: ExtractRequest) -> ActionCard:
    transcript = payload.transcript.lower()
    customer_name = "Jane Doe (AI Extracted)"
    customer_phone = "+1 555-0100"
    delivery_address = "Standard Workspace Delivery"
    delivery_time = "ASAP"
    items = [Item(name="Generic AI Item", quantity=1, price=100.00)]

    # Rule-based simulation matching typical call examples
    if "janeway" in transcript or "voyager" in transcript:
        customer_name = "Kathryn Janeway"
        customer_phone = "+1 800-VOY-0176"
        delivery_address = "Voyager Cargo Bay 1"
        delivery_time = "ASAP"
        items = [Item(name="Dilithium Crystals (Grade A)", quantity=5, price=1500.00)]
    elif "rector" in transcript or "tony" in transcript or "stark" in transcript:
        customer_name = "Tony Stark"
        customer_phone = "+1 310-555-0182"
        delivery_address = "10880 Malibu Point, CA"
        delivery_time = "Immediate"
        items = [Item(name="Palladium Core Reactor", quantity=1, price=10000.00)]
    elif "ripley" in transcript or "sulaco" in transcript:
        customer_name = "Ellen Ripley"
        customer_phone = "+1 800-555-8299"
        delivery_address = "USS Sulaco Cargo Bay 2"
        delivery_time = "ASAP before launch"
        items = [Item(name="M41A Pulse Rifle", quantity=4, price=899.99)]

    card_data = {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "items": items,
        "delivery_address": delivery_address,
        "delivery_time": delivery_time,
        "status": "pending",
        "source": payload.source,
        "transcript": payload.transcript
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
