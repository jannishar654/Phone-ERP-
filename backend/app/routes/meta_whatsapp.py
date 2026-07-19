import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from app.config.settings import settings
from app.services.meta_whatsapp_service import meta_whatsapp_service


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

    queued = 0
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "messages":
                continue
            value = change.get("value") or {}
            phone_number_id = str(
                (value.get("metadata") or {}).get("phone_number_id") or ""
            )
            contacts = {
                str(contact.get("wa_id")): contact
                for contact in value.get("contacts") or []
                if contact.get("wa_id")
            }
            for message in value.get("messages") or []:
                if not phone_number_id:
                    logger.warning("Meta WhatsApp event has no phone_number_id")
                    continue
                contact = contacts.get(str(message.get("from")))
                background_tasks.add_task(
                    meta_whatsapp_service.process_message,
                    phone_number_id,
                    message,
                    contact,
                )
                queued += 1

    return {"received": True, "queued": queued}
