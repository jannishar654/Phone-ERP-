from fastapi import APIRouter, Request, Header, HTTPException, status
import logging
from app.config.settings import settings
from app.services.telegram_connection_service import telegram_connection_service
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram"])


@router.post("/webhook/{connection_id}")
async def connected_telegram_webhook(
    connection_id: str,
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
):
    connection = telegram_connection_service.resolve_connection(connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    if not telegram_connection_service.verify_webhook_secret(
        connection, x_telegram_bot_api_secret_token or ""
    ):
        logger.warning(
            "Telegram webhook secret rejected connection_id=%s", connection_id
        )
        raise HTTPException(status_code=401, detail="Invalid secret token")

    payload = await request.json()
    update_id = payload.get("update_id")
    logger.info(
        "Telegram webhook accepted connection_id=%s update_id=%s",
        connection_id,
        update_id,
    )
    try:
        telegram_connection_service.mark_webhook_received(connection_id)
    except Exception as exc:
        logger.warning(
            "Telegram webhook timestamp update failed connection_id=%s error_type=%s",
            connection_id,
            type(exc).__name__,
        )
    try:
        await telegram_service.process_update(payload, connection=connection)
    except Exception as exc:
        logger.exception(
            "Connected Telegram update failed connection_id=%s error_type=%s",
            connection_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503, detail="Telegram update could not be processed"
        ) from exc
    return {"status": "ok"}

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
    logger.info("Legacy Telegram webhook accepted update_id=%s", payload.get("update_id"))
    
    # Process asynchronously or blockingly (depends on latency requirements, but we keep it simple here)
    await telegram_service.process_update(payload)
    
    return {"status": "ok"}
