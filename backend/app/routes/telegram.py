from fastapi import APIRouter, Request
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram"])

@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Placeholder for Telegram webhook.
    Currently just logs the payload.
    """
    payload = await request.json()
    logger.info(f"Received telegram webhook payload: {payload}")
    return {"status": "ok"}
