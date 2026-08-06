import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.dependencies.auth import get_current_user_id
from app.routes.catalog import get_user_shop_id
from app.schemas.telegram_integration import (
    TelegramConnectRequest,
    TelegramConnectionStatusResponse,
    TelegramHealthCheckResponse,
)
from app.services.telegram_connection_service import telegram_connection_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations/telegram", tags=["Telegram Integrations"])


def _owner_context(user_id: str) -> tuple[str, str]:
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id, get_user_shop_id(user_id)


def _safe_error(exc: Exception) -> HTTPException:
    code = str(exc) if isinstance(exc, RuntimeError) else "IntegrationUnavailable"
    status_map = {
        "DatabaseUnavailable": 503,
        "TelegramWebhookUrlInvalid": 503,
        "TelegramTokenInvalid": 400,
        "TelegramBotAlreadyConnected": 409,
        "DisconnectCurrentBotFirst": 409,
        "NoActiveTelegramConnection": 404,
    }
    public_messages = {
        "DatabaseUnavailable": "Telegram integration is temporarily unavailable.",
        "TelegramWebhookUrlInvalid": "Telegram webhook URL is not configured correctly.",
        "TelegramTokenInvalid": "This Telegram bot token is invalid.",
        "TelegramBotAlreadyConnected": "This Telegram bot is already connected to another business.",
        "DisconnectCurrentBotFirst": "Disconnect the current Telegram bot before connecting another one.",
        "NoActiveTelegramConnection": "No active Telegram bot connection was found.",
    }
    if code.startswith("Integration credential encryption"):
        return HTTPException(
            status_code=503,
            detail="Secure credential storage is not configured.",
        )
    return HTTPException(
        status_code=status_map.get(code, 502),
        detail=public_messages.get(
            code, "Telegram connection could not be completed. Please retry."
        ),
    )


@router.get("/status", response_model=TelegramConnectionStatusResponse)
def connection_status(user_id: str = Depends(get_current_user_id)):
    _, shop_id = _owner_context(user_id)
    try:
        return telegram_connection_service.get_status(shop_id)
    except Exception as exc:
        raise _safe_error(exc) from exc


@router.post("/connection", response_model=TelegramConnectionStatusResponse)
async def connect(
    data: TelegramConnectRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    user_id, shop_id = _owner_context(user_id)
    try:
        return await telegram_connection_service.connect(
            shop_id=shop_id,
            user_id=user_id,
            bot_token=data.bot_token.get_secret_value(),
            base_url=str(request.base_url),
        )
    except Exception as exc:
        logger.warning("Telegram connection failed error_type=%s", type(exc).__name__)
        raise _safe_error(exc) from exc


@router.post("/health-check", response_model=TelegramHealthCheckResponse)
async def health_check(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    user_id, shop_id = _owner_context(user_id)
    try:
        return await telegram_connection_service.health_check(
            shop_id, user_id, str(request.base_url)
        )
    except Exception as exc:
        raise _safe_error(exc) from exc


@router.delete("/connection", status_code=204)
async def disconnect(user_id: str = Depends(get_current_user_id)):
    user_id, shop_id = _owner_context(user_id)
    try:
        await telegram_connection_service.disconnect(shop_id, user_id)
    except Exception as exc:
        raise _safe_error(exc) from exc
    return None
