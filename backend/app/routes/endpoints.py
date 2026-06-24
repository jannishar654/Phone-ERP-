from fastapi import APIRouter, UploadFile, File, HTTPException, status, Form, Depends
from typing import List, Dict, Any, Optional
from app.dependencies.auth import get_current_user_id
from app.schemas.action_card import ActionCard, Item, ActionCardCreate, ActionCardUpdate, StatusUpdate
from app.controllers.action_card import ActionCardController
from pydantic import BaseModel
from datetime import datetime
from app.services.gemini import GeminiService
from google.genai import errors
from app.config.settings import settings

import logging

from app.routes import catalog, orders, telegram

logger = logging.getLogger(__name__)
router = APIRouter()

router.include_router(catalog.router)
router.include_router(orders.router)
router.include_router(telegram.router)

class ExtractRequest(BaseModel):
    transcript: str
    source: str = "text"
    stt_provider: Optional[str] = "gemini"
    extraction_provider: Optional[str] = "gemini"
    pipeline: Optional[str] = "gemini_gemini"

def _safe_items_from_extracted(extracted: Dict[str, Any], shop_id: Optional[str] = None) -> List[Item]:
    raw_items = extracted.get("items", []) or []
    aggregated_items = {}
    
    from app.services.matching_service import matching_service
    
    for it in raw_items:
        try:
            name = (it.get("name") or "").strip() if isinstance(it, dict) else str(it)
            if not name:
                name = "Unknown Item"

            qty_raw = it.get("quantity") if isinstance(it, dict) else None
            if qty_raw is not None:
                try:
                    qty = float(qty_raw)
                except Exception:
                    qty = None
            else:
                qty = None

            unit = (it.get("unit") or "") if isinstance(it, dict) else ""
            if str(unit).strip().lower() in ["none", "null", "missing", "unknown"]:
                unit = ""

            price = None
            price_status = "Pending Price Verification"
            canonical_name = None
            resolution_status = "unmatched"
            possible_matches = []

            # 1. Real Catalog Matching using shop_id
            if shop_id:
                matched = matching_service.match_product(name, shop_id)
                resolution_status = matched.get("resolution_status", "unmatched")
                canonical_name = matched.get("canonical_name")
                possible_matches = matched.get("possible_matches", [])
                if resolution_status in ["matched", "suggested"]:
                    price = matched.get("unit_price")
                    if matched.get("unit"):
                        unit = matched.get("unit")
                    price_status = "Verified"

            # 2. Fallback if not matched but AI provided a price (not trusted, but kept)
            if price is None and isinstance(it, dict) and it.get("price") is not None:
                try:
                    price = float(it.get("price"))
                except Exception:
                    pass

            final_name = canonical_name or name
            
            if final_name in aggregated_items:
                existing = aggregated_items[final_name]
                if existing["quantity"] is not None and qty is not None:
                    existing["quantity"] += qty
                elif qty is not None:
                    existing["quantity"] = qty
            else:
                aggregated_items[final_name] = {
                    "name": final_name,
                    "raw_name": name,
                    "quantity": qty if qty is not None else None,
                    "unit": unit,
                    "price": price,
                    "price_status": price_status,
                    "canonical_name": canonical_name,
                    "resolution_status": resolution_status,
                    "possible_matches": possible_matches
                }
        except Exception:
            if "Unknown Item" not in aggregated_items:
                aggregated_items["Unknown Item"] = {"name": "Unknown Item", "quantity": None, "unit": "", "price": None}
            pass

    try:
        return [Item(**item) for item in aggregated_items.values()]
    except Exception:
        return [Item(name="Unknown Item", quantity=None, price=None)]

def _create_card_from_extracted(
    extracted: Dict[str, Any],
    source: str,
    stt_provider: Optional[str],
    extraction_provider: Optional[str],
    pipeline: Optional[str],
    transcript: str,
    user_id: Optional[str] = None,
) -> ActionCard:
    shop_id = None
    if user_id:
        from app.services.supabase import supabase_client
        if supabase_client is not None:
            try:
                res = supabase_client.table("shops").select("id").eq("owner_id", user_id).execute()
                if res.data:
                    shop_id = res.data[0]["id"]
            except Exception:
                pass

    items = _safe_items_from_extracted(extracted, shop_id)
    
    # Clean up stale catalog warnings if items are now matched
    validation_warnings = extracted.get("validation_warnings", [])
    final_warnings = []
    matched_names = [i.get("raw_name", i.get("name")) for i in items if i.get("resolution_status") in ("matched", "suggested") or (i.get("price") is not None and i.get("price") > 0)]
    for w in validation_warnings:
        if "No catalog match found" in w or "Ambiguous product" in w:
            is_stale = False
            for mn in matched_names:
                if mn and (f"'{mn}'" in w or f"'{mn.lower()}'" in w.lower()):
                    is_stale = True
                    break
            if is_stale:
                continue
        final_warnings.append(w)

    card_data = {
        "shop_id": shop_id,
        "customer_name": extracted.get("customer_name", "Unknown"),
        "customer_phone": extracted.get("customer_phone", ""),
        "items": items,
        "delivery_address": extracted.get("delivery_address", ""),
        "delivery_time": extracted.get("delivery_time", ""),
        "delivery_time_raw": extracted.get("delivery_time_raw"),
        "delivery_time_normalized": extracted.get("delivery_time_normalized"),
        "delivery_time_confidence": extracted.get("delivery_time_confidence"),
        "delivery_time_warning": extracted.get("delivery_time_warning"),
        "risk_flags": extracted.get("risk_flags", []),
        "missing_fields": extracted.get("missing_fields", []),
        "validation_warnings": final_warnings,
        "payment_method": extracted.get("payment_method"),
        "status": "pending",
        "source": source,
        "message_type": extracted.get("type", "ORDER"),
        "confidence": extracted.get("confidence", 0.0),
        "stt_provider": stt_provider,
        "extraction_provider": extraction_provider,
        "metadata": {
            "pipeline": pipeline,
            "extraction_notes": extracted.get("extraction_notes", ""),
            "multi_card_notes": "Multiple cards returned but currently only using the first card in UI." if extracted.get("_multi_card_flag") else "",
            **(extracted.get("metadata", {}) if isinstance(extracted.get("metadata"), dict) else {}),
        },
        "transcript": transcript,
    }

    from app.services.confidence_scorer import ConfidenceScorer
    score, label, reasons = ConfidenceScorer.calculate_confidence(card_data)
    card_data["confidence_score"] = score
    card_data["confidence_label"] = label
    card_data["confidence_reasons"] = reasons

    return ActionCardController.create_card(card_data, user_id)

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
async def transcribe_audio(file: UploadFile = File(...), provider: str = Form(settings.STT_PROVIDER)) -> Dict[str, Any]:
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

    MAX_FILE_SIZE = 20 * 1024 * 1024 # 20 MB
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file exceeds the maximum allowed size of 20MB.",
        )

    try:
        if provider == "sarvam":
            from app.services.sarvam import SarvamService
            transcript = await SarvamService.transcribe_audio_file(
                file_content=file_content,
                filename=file.filename,
            )
        else:
            transcript = await GeminiService.transcribe_audio_file(
                file_content=file_content,
                filename=file.filename,
            )
    except Exception as error:
        err_msg = str(error).upper()
        is_quota = False
        if isinstance(error, errors.APIError) and (error.code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "QUOTA" in err_msg):
            is_quota = True
        elif "429" in err_msg or "402" in err_msg or "PAYMENT REQUIRED" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "QUOTA" in err_msg:
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

@router.post("/extract-action-card-audio", response_model=ActionCard, status_code=status.HTTP_201_CREATED)
async def extract_action_card_audio(
    file: UploadFile = File(...),
    pipeline: str = Form("gemini_audio_extraction"),
    user_id: Optional[str] = Depends(get_current_user_id),
) -> ActionCard:
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

    MAX_FILE_SIZE = 20 * 1024 * 1024
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file exceeds the maximum allowed size of 20MB.",
        )

    try:
        extracted = await GeminiService.extract_order_details_from_audio(
            file_content=file_content,
            filename=file.filename,
            pipeline=pipeline,
        )
        logger.info(f"Direct audio extraction (INFO): Pipeline={pipeline}, Items={len(extracted.get('items', []))}, Success=True")
    except Exception as error:
        err_msg = str(error).upper()
        if "429" in err_msg or "402" in err_msg or "PAYMENT REQUIRED" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "QUOTA" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Voice processing is temporarily unavailable due to API quota limits. Please enter the order manually.",
            ) from error

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    transcript = str(
        extracted.get("transcript")
        or extracted.get("metadata", {}).get("transcript_original", "")
    )
    return _create_card_from_extracted(
        extracted,
        source="audio",
        stt_provider="gemini_audio",
        extraction_provider="gemini",
        pipeline=pipeline,
        transcript=transcript,
        user_id=user_id,
    )
# Entity extraction endpoint
@router.post("/extract-action-card", response_model=ActionCard, status_code=status.HTTP_201_CREATED)
async def extract_action_card(payload: ExtractRequest, user_id: Optional[str] = Depends(get_current_user_id)) -> ActionCard:
    try:
        extracted = await GeminiService.extract_order_details(
            payload.transcript,
            stt_provider=payload.stt_provider,
            extraction_provider=payload.extraction_provider,
            pipeline=payload.pipeline
        )
        logger.info(f"Extracted data (INFO): Pipeline={payload.pipeline}, Items={len(extracted.get('items', []))}, Success=True")
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    transcript = str(
        extracted.get("transcript")
        or extracted.get("metadata", {}).get("transcript_original", "")
        or payload.transcript
    )
    return _create_card_from_extracted(
        extracted,
        source=payload.source,
        stt_provider=payload.stt_provider,
        extraction_provider=payload.extraction_provider,
        pipeline=payload.pipeline,
        transcript=transcript,
        user_id=user_id,
    )

# Get all orders/cards
@router.get("/action-cards", response_model=List[ActionCard], status_code=status.HTTP_200_OK)
async def get_action_cards(user_id: Optional[str] = Depends(get_current_user_id)) -> List[ActionCard]:
    return ActionCardController.get_all_cards(user_id)

# Get card by ID
@router.get("/action-cards/{card_id}", response_model=ActionCard, status_code=status.HTTP_200_OK)
async def get_action_card(card_id: str, user_id: Optional[str] = Depends(get_current_user_id)) -> ActionCard:
    card = ActionCardController.get_card_by_id(card_id, user_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ActionCard with ID {card_id} not found"
        )
    return card

# Create manual card
@router.post("/action-cards", response_model=ActionCard, status_code=status.HTTP_201_CREATED)
async def create_action_card(payload: ActionCardCreate, user_id: Optional[str] = Depends(get_current_user_id)) -> ActionCard:
    return ActionCardController.create_card(payload.model_dump(), user_id)

# Edit card
@router.put("/action-cards/{card_id}", response_model=ActionCard, status_code=status.HTTP_200_OK)
async def update_action_card(card_id: str, payload: ActionCardUpdate, user_id: Optional[str] = Depends(get_current_user_id)) -> ActionCard:
    updated_card = ActionCardController.update_card(card_id, payload.model_dump(exclude_unset=True), user_id)
    if not updated_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ActionCard with ID {card_id} not found"
        )
    return updated_card

# Quick status update
@router.patch("/action-cards/{card_id}/status", response_model=ActionCard, status_code=status.HTTP_200_OK)
async def update_action_card_status(card_id: str, payload: StatusUpdate, user_id: Optional[str] = Depends(get_current_user_id)) -> ActionCard:
    updated_card = ActionCardController.update_card_status(card_id, payload.status, user_id)
    if not updated_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ActionCard with ID {card_id} not found"
        )
    return updated_card

# Delete card
@router.delete("/action-cards/{card_id}", status_code=status.HTTP_200_OK)
async def delete_action_card(card_id: str, user_id: Optional[str] = Depends(get_current_user_id)):
    success = ActionCardController.delete_card(card_id, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ActionCard with ID {card_id} not found"
        )
    return {"message": f"ActionCard {card_id} deleted successfully"}
