from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies.auth import get_current_user_id
from app.routes.catalog import get_user_shop_id
from app.services.supabase import supabase_client


router = APIRouter(prefix="/owner-notifications", tags=["Owner Notifications"])


class OwnerNotification(BaseModel):
    id: str
    notification_type: Literal["new_order", "order_reminder", "customer_request"]
    title: str
    message: str
    scheduled_at: str
    action_card_id: Optional[str] = None
    customer_request_id: Optional[str] = None


@router.get("", response_model=List[OwnerNotification])
def list_due_owner_notifications(
    user_id: str = Depends(get_current_user_id),
):
    shop_id = get_user_shop_id(user_id)
    result = (
        supabase_client.table("owner_notifications")
        .select(
            "id, notification_type, title, message, scheduled_at, "
            "action_card_id, customer_request_id"
        )
        .eq("shop_id", shop_id)
        .is_("acknowledged_at", "null")
        .is_("dismissed_at", "null")
        .lte("scheduled_at", datetime.now(timezone.utc).isoformat())
        .order("scheduled_at")
        .limit(50)
        .execute()
    )
    return result.data or []


@router.post("/{notification_id}/ack", response_model=OwnerNotification)
def acknowledge_owner_notification(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
):
    shop_id = get_user_shop_id(user_id)
    updated = (
        supabase_client.table("owner_notifications")
        .update({"acknowledged_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", notification_id)
        .eq("shop_id", shop_id)
        .is_("acknowledged_at", "null")
        .is_("dismissed_at", "null")
        .execute()
    )
    if not updated.data:
        existing = (
            supabase_client.table("owner_notifications")
            .select(
                "id, notification_type, title, message, scheduled_at, "
                "action_card_id, customer_request_id"
            )
            .eq("id", notification_id)
            .eq("shop_id", shop_id)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Notification not found")
        return existing.data[0]
    return updated.data[0]
