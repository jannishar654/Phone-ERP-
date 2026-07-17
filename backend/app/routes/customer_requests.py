import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user_id
from app.routes.catalog import get_user_shop_id
from app.services.supabase import supabase_client


router = APIRouter(prefix="/customer-requests", tags=["Customer Requests"])


class CustomerRequestDecision(BaseModel):
    status: Literal["approved", "rejected", "resolved"]
    owner_note: Optional[str] = Field(default=None, max_length=2000)


def _create_review_action_card(
    request: Dict[str, Any], user_id: str
) -> str:
    existing = (
        supabase_client.table("action_cards")
        .select("id")
        .eq("customer_request_id", request["id"])
        .eq("shop_id", request["shop_id"])
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]

    order = (
        supabase_client.table("orders")
        .select("*, order_items(*)")
        .eq("id", request["order_id"])
        .eq("shop_id", request["shop_id"])
        .eq("customer_id", request["customer_id"])
        .execute()
    )
    if not order.data:
        raise HTTPException(status_code=404, detail="Original order not found")
    original = order.data[0]
    customer = (
        supabase_client.table("customers")
        .select("name, phone, address")
        .eq("id", request["customer_id"])
        .eq("shop_id", request["shop_id"])
        .execute()
    )
    customer_data = customer.data[0] if customer.data else {}
    action = "change" if request["request_type"] == "change_order" else "repeat"
    card_id = f"ac_{action}_{uuid.uuid4().hex[:12]}"
    items = [
        {
            "name": item.get("display_name") or item.get("raw_name") or "Item",
            "raw_name": item.get("raw_name"),
            "quantity": item.get("quantity"),
            "unit": item.get("unit"),
            "price": item.get("unit_price"),
            "resolution_status": "matched" if item.get("catalog_item_id") else "unmatched",
        }
        for item in original.get("order_items", [])
    ]
    card_payload = {
        "id": card_id,
        "customer_request_id": request["id"],
        "user_id": user_id,
        "shop_id": request["shop_id"],
        "customer_id": request["customer_id"],
        "customer_name": original.get("customer_name") or customer_data.get("name"),
        "customer_phone": original.get("customer_phone") or customer_data.get("phone"),
        "delivery_address": original.get("delivery_address") or customer_data.get("address"),
        "payment_method": original.get("payment_method"),
        "items": items,
        "status": "pending",
        "source": "customer_portal",
        "message_type": "ORDER",
        "transcript": (
            "Customer requested changes to a previous order: "
            f"{request.get('message') or 'No details supplied.'}"
            if action == "change"
            else "Customer requested a repeat of a previous order."
        ),
        "metadata": {
            "customer_request_id": request["id"],
            f"{action}_of_order_id": request["order_id"],
            "requested_change": request.get("message") if action == "change" else None,
        },
    }
    try:
        created = (
            supabase_client.table("action_cards")
            .insert(card_payload)
            .execute()
        )
    except Exception:
        existing = (
            supabase_client.table("action_cards")
            .select("id")
            .eq("customer_request_id", request["id"])
            .eq("shop_id", request["shop_id"])
            .execute()
        )
        if existing.data:
            return existing.data[0]["id"]
        raise
    if not created.data:
        raise HTTPException(status_code=500, detail="Failed to create repeat order review card")
    return card_id


@router.get("")
def list_customer_requests(
    status: str = "pending",
    user_id: str = Depends(get_current_user_id),
):
    shop_id = get_user_shop_id(user_id)
    query = (
        supabase_client.table("customer_requests")
        .select("*")
        .eq("shop_id", shop_id)
        .order("created_at", desc=True)
    )
    if status != "all":
        query = query.eq("status", status)
    result = query.limit(100).execute()
    requests = result.data or []
    if not requests:
        return []

    customer_ids = list({
        request["customer_id"]
        for request in requests
        if request.get("customer_id")
    })
    order_ids = list({
        request["order_id"]
        for request in requests
        if request.get("order_id")
    })

    customers_by_id: Dict[str, Dict[str, Any]] = {}
    if customer_ids:
        customers = (
            supabase_client.table("customers")
            .select("id, name, phone")
            .eq("shop_id", shop_id)
            .in_("id", customer_ids)
            .execute()
        )
        customers_by_id = {
            customer["id"]: customer for customer in customers.data or []
        }

    orders_by_id: Dict[str, Dict[str, Any]] = {}
    if order_ids:
        orders = (
            supabase_client.table("orders")
            .select("id, order_number, lifecycle_status, total_amount")
            .eq("shop_id", shop_id)
            .in_("id", order_ids)
            .execute()
        )
        orders_by_id = {order["id"]: order for order in orders.data or []}

    return [
        {
            **request,
            "customers": customers_by_id.get(request.get("customer_id")),
            "orders": orders_by_id.get(request.get("order_id")),
        }
        for request in requests
    ]


@router.patch("/{request_id}")
def decide_customer_request(
    request_id: str,
    decision: CustomerRequestDecision,
    user_id: str = Depends(get_current_user_id),
):
    shop_id = get_user_shop_id(user_id)
    result = (
        supabase_client.table("customer_requests")
        .select("*")
        .eq("id", request_id)
        .eq("shop_id", shop_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Customer request not found")
    request = result.data[0]
    if request.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Customer request was already handled")

    is_support = request.get("request_type") == "support"
    if is_support and decision.status == "approved":
        raise HTTPException(status_code=422, detail="Support requests must be resolved or rejected")
    if not is_support and decision.status == "resolved":
        raise HTTPException(status_code=422, detail="Order requests must be approved or rejected")

    if decision.status == "approved" and request["request_type"] == "cancel_order":
        try:
            cancelled = supabase_client.rpc(
                "approve_customer_cancellation",
                {
                    "p_request_id": request_id,
                    "p_shop_id": shop_id,
                    "p_owner_note": decision.owner_note,
                },
            ).execute()
        except Exception as exc:
            raise HTTPException(
                status_code=409,
                detail="Order can no longer be cancelled or the request was already handled",
            ) from exc
        if not cancelled.data:
            raise HTTPException(status_code=409, detail="Cancellation could not be applied")
        return cancelled.data[0]

    claimed = (
        supabase_client.table("customer_requests")
        .update({"status": "processing"})
        .eq("id", request_id)
        .eq("shop_id", shop_id)
        .eq("status", "pending")
        .execute()
    )
    if not claimed.data:
        raise HTTPException(status_code=409, detail="Customer request is being handled")
    request = {**request, **claimed.data[0]}

    payload = dict(request.get("payload") or {})
    try:
        if decision.status == "approved" and request["request_type"] in {
            "repeat_order", "change_order"
        }:
            payload["action_card_id"] = _create_review_action_card(request, user_id)
        updates = {
            "status": decision.status,
            "owner_note": decision.owner_note,
            "payload": payload,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }
        updated = (
            supabase_client.table("customer_requests")
            .update(updates)
            .eq("id", request_id)
            .eq("shop_id", shop_id)
            .eq("status", "processing")
            .execute()
        )
        if not updated.data:
            raise HTTPException(status_code=409, detail="Customer request state changed")
        return updated.data[0]
    except Exception:
        (
            supabase_client.table("customer_requests")
            .update({"status": "pending"})
            .eq("id", request_id)
            .eq("shop_id", shop_id)
            .eq("status", "processing")
            .execute()
        )
        raise
