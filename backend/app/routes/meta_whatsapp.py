import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from app.config.settings import settings
from app.services.meta_whatsapp_event_service import meta_whatsapp_event_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meta/whatsapp", tags=["Meta WhatsApp"])


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_meta_whatsapp_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if not settings.META_WHATSAPP_VERIFY_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meta webhook verification is not configured",
        )
    if (
        mode == "subscribe"
        and challenge is not None
        and hmac.compare_digest(token or "", settings.META_WHATSAPP_VERIFY_TOKEN)
    ):
        return challenge
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid verify token")


def _verify_signature(raw_body: bytes, signature: str) -> bool:
    if not settings.META_APP_SECRET or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        settings.META_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def receive_meta_whatsapp_webhook(
    request: Request, background_tasks: BackgroundTasks
):
    raw_body = await request.body()
    if len(raw_body) > settings.META_WHATSAPP_MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail="Webhook payload is too large")
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(raw_body, signature):
        logger.warning("Rejected Meta WhatsApp webhook with invalid signature")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    if payload.get("object") != "whatsapp_business_account":
        return {"received": True, "queued": 0}

    try:
        event_ids = meta_whatsapp_event_service.persist_webhook_payload(payload)
    except Exception as exc:
        logger.exception(
            "Meta webhook persistence failed error_type=%s", type(exc).__name__
        )
        # Returning a retryable error is safer than acknowledging an event that
        # was never stored. Meta can redeliver the signed webhook.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook persistence is temporarily unavailable",
        ) from exc

    for event_id in event_ids:
        background_tasks.add_task(
            meta_whatsapp_event_service.process_event, event_id
        )

    return {"received": True, "queued": len(event_ids)}
