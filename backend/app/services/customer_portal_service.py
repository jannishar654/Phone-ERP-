import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.config.settings import settings
from app.services.supabase import supabase_client
from app.utils.security import hash_token


MAGIC_LINK_TTL_MINUTES = 15
PORTAL_SESSION_TTL_HOURS = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def create_customer_portal_magic_link(
    shop_id: str,
    customer_id: str,
    channel: str,
    db_client=None,
) -> str:
    if not shop_id or not customer_id:
        raise ValueError("shop_id and customer_id are required")
    client = db_client or supabase_client
    if client is None:
        raise RuntimeError("Database client is not configured")

    raw_token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(minutes=MAGIC_LINK_TTL_MINUTES)
    result = client.rpc(
        "issue_customer_portal_magic_link",
        {
            "p_shop_id": str(shop_id),
            "p_customer_id": str(customer_id),
            "p_channel": str(channel),
            "p_token_hash": hash_token(raw_token),
            "p_expires_at": expires_at.isoformat(),
        },
    ).execute()
    if not result.data:
        raise RuntimeError("Failed to create customer portal link")

    base_url = settings.FRONTEND_PUBLIC_BASE_URL.rstrip("/")
    # URL fragments are not sent to Vercel or included in HTTP access logs.
    # The browser exchanges the one-time token directly with the API.
    return f"{base_url}/customer/access#token={raw_token}"


def exchange_magic_link(raw_token: str, db_client=None) -> Dict[str, Any]:
    client = db_client or supabase_client
    if client is None:
        raise RuntimeError("Database client is not configured")

    raw_session = secrets.token_urlsafe(48)
    expires_at = _now() + timedelta(hours=PORTAL_SESSION_TTL_HOURS)
    try:
        exchange = client.rpc(
            "exchange_customer_portal_magic_link",
            {
                "p_token_hash": hash_token(raw_token),
                "p_session_hash": hash_token(raw_session),
                "p_session_expires_at": expires_at.isoformat(),
            },
        ).execute()
    except Exception as exc:
        message = str(exc)
        for error_code in ("link_used", "link_expired", "invalid_link"):
            if error_code in message:
                raise ValueError(error_code) from exc
        raise RuntimeError("Failed to exchange customer portal link") from exc
    if not exchange.data:
        raise ValueError("invalid_link")
    record = exchange.data[0]
    return {
        "session_token": raw_session,
        "expires_at": expires_at,
        "shop_id": record["shop_id"],
        "customer_id": record["customer_id"],
    }


def validate_customer_session(raw_session: str, db_client=None) -> Dict[str, Any]:
    if not raw_session:
        raise ValueError("missing_session")
    client = db_client or supabase_client
    if client is None:
        raise RuntimeError("Database client is not configured")
    result = (
        client.table("customer_portal_sessions")
        .select("id, shop_id, customer_id, expires_at, revoked_at")
        .eq("token_hash", hash_token(raw_session))
        .execute()
    )
    if not result.data:
        raise ValueError("invalid_session")
    session = result.data[0]
    if session.get("revoked_at") or _parse_datetime(session["expires_at"]) <= _now():
        raise ValueError("session_expired")
    (
        client.table("customer_portal_sessions")
        .update({"last_used_at": _now().isoformat()})
        .eq("id", session["id"])
        .execute()
    )
    return session


def revoke_customer_session(raw_session: str, db_client=None) -> None:
    client = db_client or supabase_client
    if client is None or not raw_session:
        return
    (
        client.table("customer_portal_sessions")
        .update({"revoked_at": _now().isoformat()})
        .eq("token_hash", hash_token(raw_session))
        .execute()
    )
