from fastapi import APIRouter, Request, Header, HTTPException, status
import logging
from app.config.settings import settings
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram"])

@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """
    Telegram webhook endpoint.
    """
    # Validate secret token if configured
    if settings.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
            logger.warning("Invalid or missing Telegram webhook secret token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid secret token"
            )
            
    payload = await request.json()
    logger.info(f"Received telegram webhook payload: {payload}")
    
    # Process asynchronously or blockingly (depends on latency requirements, but we keep it simple here)
    await telegram_service.process_update(payload)
    
    return {"status": "ok"}
