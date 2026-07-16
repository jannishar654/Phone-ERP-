from datetime import datetime, timedelta, timezone

from app.config.settings import settings
from app.services.supabase import supabase_client
from app.utils.security import generate_deterministic_bill_token, hash_token


def ensure_public_bill_link(
    order_id: str,
    shop_id: str,
    expires_in_days: int = 30,
    db_client=None,
) -> str:
    """Create or refresh one deterministic public bill link for an order."""
    if not order_id or not shop_id:
        raise ValueError("order_id and shop_id are required")

    client = db_client or supabase_client
    if client is None:
        raise RuntimeError("Database client is not configured")

    raw_token = generate_deterministic_bill_token(str(order_id), str(shop_id))
    token_hash = hash_token(raw_token)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    ).isoformat()

    existing = (
        client.table("order_public_links")
        .select("id")
        .eq("order_id", str(order_id))
        .eq("shop_id", str(shop_id))
        .execute()
    )
    payload = {"token_hash": token_hash, "expires_at": expires_at}
    if existing.data:
        (
            client.table("order_public_links")
            .update(payload)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    else:
        (
            client.table("order_public_links")
            .insert(
                {
                    "order_id": str(order_id),
                    "shop_id": str(shop_id),
                    **payload,
                }
            )
            .execute()
        )

    base_url = settings.FRONTEND_PUBLIC_BASE_URL.rstrip("/")
    return f"{base_url}/bill/{raw_token}"
