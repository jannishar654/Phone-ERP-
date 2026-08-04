import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.auth import get_current_user_id
from app.routes.catalog import get_user_shop_id
from app.schemas.whatsapp_integration import (
    WhatsAppConnectionStatusResponse,
    WhatsAppHealthCheckResponse,
    WhatsAppOnboardingCallbackRequest,
    WhatsAppOnboardingSessionResponse,
)
from app.services.meta_whatsapp_onboarding_service import (
    meta_whatsapp_onboarding_service,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations/whatsapp", tags=["WhatsApp Integrations"])


def _owner_context(user_id: str) -> tuple[str, str]:
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id, get_user_shop_id(user_id)


def _safe_error(exc: Exception) -> HTTPException:
    code = str(exc) if isinstance(exc, RuntimeError) else "IntegrationUnavailable"
    status_map = {
        "EmbeddedSignupDisabled": 503,
        "EmbeddedSignupNotConfigured": 503,
        "DatabaseUnavailable": 503,
        "InvalidOrExpiredOnboardingSession": 400,
        "MetaPermissionsMissing": 403,
        "WabaNotGranted": 403,
        "PhoneNotGranted": 403,
        "PhoneAlreadyConnected": 409,
        "WabaAlreadyConnected": 409,
        "DisconnectCurrentNumberFirst": 409,
        "PhoneSelectionRequired": 409,
        "NoActiveConnection": 404,
    }
    public_messages = {
        "EmbeddedSignupDisabled": "WhatsApp onboarding is not enabled yet.",
        "EmbeddedSignupNotConfigured": "WhatsApp onboarding is not configured.",
        "InvalidOrExpiredOnboardingSession": "This connection session expired. Please start again.",
        "MetaPermissionsMissing": "Meta did not grant all required WhatsApp permissions.",
        "WabaNotGranted": "The selected WhatsApp account was not granted to PhoneERP.",
        "PhoneNotGranted": "The selected WhatsApp number was not granted to PhoneERP.",
        "PhoneAlreadyConnected": "This WhatsApp number is already connected to another business.",
        "WabaAlreadyConnected": "This WhatsApp Business Account is already connected to another business.",
        "DisconnectCurrentNumberFirst": "Disconnect the current WhatsApp number before connecting another one.",
        "PhoneSelectionRequired": "Select exactly one WhatsApp phone number and try again.",
        "NoActiveConnection": "No active WhatsApp connection was found.",
    }
    return HTTPException(
        status_code=status_map.get(code, 502),
        detail=public_messages.get(
            code, "WhatsApp connection could not be completed. Please retry."
        ),
    )


@router.post(
    "/onboarding-session", response_model=WhatsAppOnboardingSessionResponse
)
def create_onboarding_session(user_id: str = Depends(get_current_user_id)):
    user_id, shop_id = _owner_context(user_id)
    try:
        return meta_whatsapp_onboarding_service.create_session(user_id, shop_id)
    except Exception as exc:
        logger.warning("WhatsApp onboarding session failed error_type=%s", type(exc).__name__)
        raise _safe_error(exc) from exc


@router.post("/callback", response_model=WhatsAppConnectionStatusResponse)
async def complete_onboarding(
    data: WhatsAppOnboardingCallbackRequest,
    user_id: str = Depends(get_current_user_id),
):
    user_id, shop_id = _owner_context(user_id)
    try:
        await meta_whatsapp_onboarding_service.complete_onboarding(
            state=data.state,
            code=data.code,
            user_id=user_id,
            shop_id=shop_id,
            waba_hint=data.waba_id,
            phone_hint=data.phone_number_id,
            registration_pin=data.registration_pin.get_secret_value(),
        )
        return meta_whatsapp_onboarding_service.get_status(shop_id)
    except Exception as exc:
        logger.warning("WhatsApp onboarding callback failed error_type=%s", type(exc).__name__)
        raise _safe_error(exc) from exc


@router.get("/status", response_model=WhatsAppConnectionStatusResponse)
def connection_status(user_id: str = Depends(get_current_user_id)):
    _, shop_id = _owner_context(user_id)
    try:
        return meta_whatsapp_onboarding_service.get_status(shop_id)
    except Exception as exc:
        raise _safe_error(exc) from exc


@router.post("/health-check", response_model=WhatsAppHealthCheckResponse)
async def health_check(user_id: str = Depends(get_current_user_id)):
    user_id, shop_id = _owner_context(user_id)
    try:
        return await meta_whatsapp_onboarding_service.health_check(shop_id, user_id)
    except Exception as exc:
        raise _safe_error(exc) from exc


@router.delete("/connection", status_code=204)
async def disconnect(user_id: str = Depends(get_current_user_id)):
    user_id, shop_id = _owner_context(user_id)
    try:
        await meta_whatsapp_onboarding_service.disconnect(shop_id, user_id)
    except Exception as exc:
        raise _safe_error(exc) from exc
    return None
