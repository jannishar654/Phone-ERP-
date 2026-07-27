import asyncio
import logging
import re
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException

from app.schemas.customer_portal import (
    CustomerAssistantRequest,
    CustomerAssistantResponse,
    CustomerDraftUpdate,
    CustomerPortalOverview,
    CustomerPortalOrder,
    CustomerPortalSessionResponse,
    CustomerRequestCreate,
    MagicLinkExchange,
)
from app.schemas.inbound import ConversationIntent, IntentClassification
from app.services.bill_link_service import ensure_public_bill_link
from app.services.customer_portal_service import (
    exchange_magic_link,
    revoke_customer_session,
    validate_customer_session,
)
from app.services.gemini import GeminiService
from app.services.intent_router import IntentRouter
from app.services.order_amendment_service import normalize_amendment_items
from app.services.supabase import supabase_client


router = APIRouter(prefix="/customer", tags=["Customer Portal"])
logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _safe_optional_query(label: str, callback) -> List[Dict[str, Any]]:
    try:
        result = callback()
        return list(result.data or [])
    except Exception as exc:
        logger.warning(
            "Customer portal optional query failed source=%s error_type=%s",
            label,
            type(exc).__name__,
        )
        return []


def _merge_unique_rows(*row_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for rows in row_groups:
        for row in rows:
            row_id = row.get("id")
            if row_id is not None:
                merged[str(row_id)] = row
    return list(merged.values())


def get_customer_context(
    x_customer_session: str | None = Header(default=None),
) -> Dict[str, Any]:
    try:
        return validate_customer_session(x_customer_session or "")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Customer session expired") from exc


def _customer_and_shop(context: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    customer = (
        supabase_client.table("customers")
        .select("id, shop_id, name, phone")
        .eq("id", context["customer_id"])
        .eq("shop_id", context["shop_id"])
        .execute()
    )
    shop = (
        supabase_client.table("shops")
        .select("id, name")
        .eq("id", context["shop_id"])
        .execute()
    )
    if not customer.data or not shop.data:
        raise HTTPException(status_code=404, detail="Customer account not found")
    return customer.data[0], shop.data[0]


def _latest_customer_order(context: Dict[str, Any]) -> Dict[str, Any] | None:
    result = (
        supabase_client.table("orders")
        .select("id, order_number, total_amount, lifecycle_status, created_at")
        .eq("shop_id", context["shop_id"])
        .eq("customer_id", context["customer_id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _create_pending_order_request(
    context: Dict[str, Any],
    order_id: str,
    request_type: str,
    message: str | None = None,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    existing = (
        supabase_client.table("customer_requests")
        .select("id, status")
        .eq("shop_id", context["shop_id"])
        .eq("customer_id", context["customer_id"])
        .eq("order_id", order_id)
        .eq("request_type", request_type)
        .in_("status", ["pending", "processing"])
        .execute()
    )
    if existing.data:
        current = existing.data[0]
        if request_type == "change_order" and current.get("status") == "pending":
            refreshed = (
                supabase_client.table("customer_requests")
                .update({"message": message, "payload": payload or {}})
                .eq("id", current["id"])
                .eq("shop_id", context["shop_id"])
                .eq("customer_id", context["customer_id"])
                .eq("status", "pending")
                .execute()
            )
            if refreshed.data:
                return {
                    **refreshed.data[0],
                    "status": "pending",
                    "duplicate": True,
                    "updated": True,
                }
            raise HTTPException(
                status_code=409,
                detail="The owner has started reviewing your previous change. Please contact the business for another update.",
            )
        if request_type == "change_order" and current.get("status") == "processing":
            raise HTTPException(
                status_code=409,
                detail="The owner is already reviewing your previous change. Please contact the business for another update.",
            )
        return {
            **current,
            "status": current.get("status") or "pending",
            "duplicate": True,
        }

    request_data = {
        "shop_id": context["shop_id"],
        "customer_id": context["customer_id"],
        "order_id": order_id,
        "request_type": request_type,
        "message": message,
        "payload": payload or {},
    }
    try:
        created = (
            supabase_client.table("customer_requests")
            .insert(request_data)
            .execute()
        )
    except Exception:
        existing = (
            supabase_client.table("customer_requests")
            .select("id, status")
            .eq("shop_id", context["shop_id"])
            .eq("customer_id", context["customer_id"])
            .eq("order_id", order_id)
            .eq("request_type", request_type)
            .in_("status", ["pending", "processing"])
            .execute()
        )
        if existing.data:
            return {
                **existing.data[0],
                "status": existing.data[0].get("status") or "pending",
                "duplicate": True,
            }
        raise
    if not created.data:
        raise HTTPException(status_code=500, detail="Failed to create request")
    return created.data[0]


@router.post("/access/exchange", response_model=CustomerPortalSessionResponse)
def exchange_customer_access(payload: MagicLinkExchange):
    try:
        session = exchange_magic_link(payload.token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="This access link is invalid or expired") from exc
    except RuntimeError as exc:
        logger.error("Customer portal exchange unavailable (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Customer portal is temporarily unavailable. Please try again shortly.",
        ) from exc
    customer, shop = _customer_and_shop(session)
    return CustomerPortalSessionResponse(
        session_token=session["session_token"],
        expires_at=session["expires_at"],
        customer_name=customer.get("name") or "Customer",
        shop_name=shop.get("name") or "Business",
    )


@router.post("/access/logout")
def logout_customer(
    x_customer_session: str | None = Header(default=None),
):
    revoke_customer_session(x_customer_session or "")
    return {"message": "Signed out"}


@router.get("/orders", response_model=CustomerPortalOverview)
def get_customer_orders(context: Dict[str, Any] = Depends(get_customer_context)):
    customer, shop = _customer_and_shop(context)
    customer_orders = (
        supabase_client.table("orders")
        .select("*")
        .eq("shop_id", context["shop_id"])
        .eq("customer_id", context["customer_id"])
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    ).data or []
    legacy_orders: List[Dict[str, Any]] = []
    customer_phone = customer.get("phone")
    if customer_phone:
        legacy_orders = _safe_optional_query(
            "legacy_orders_by_phone",
            lambda: (
                supabase_client.table("orders")
                .select("*")
                .eq("shop_id", context["shop_id"])
                .eq("customer_phone", customer_phone)
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            ),
        )
    order_rows = _merge_unique_rows(customer_orders, legacy_orders)
    order_rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    order_rows = order_rows[:50]
    order_ids = [str(order["id"]) for order in order_rows]

    items_by_order: Dict[str, List[Dict[str, Any]]] = {
        order_id: [] for order_id in order_ids
    }
    if order_ids:
        item_rows = _safe_optional_query(
            "order_items",
            lambda: (
                supabase_client.table("order_items")
                .select("*")
                .in_("order_id", order_ids)
                .execute()
            ),
        )
        for item in item_rows:
            items_by_order.setdefault(str(item.get("order_id")), []).append(item)

    customer_cards = _safe_optional_query(
        "action_cards",
        lambda: (
            supabase_client.table("action_cards")
            .select("*")
            .eq("shop_id", context["shop_id"])
            .eq("customer_id", context["customer_id"])
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        ),
    )
    legacy_cards: List[Dict[str, Any]] = []
    if customer_phone:
        legacy_cards = _safe_optional_query(
            "legacy_action_cards_by_phone",
            lambda: (
                supabase_client.table("action_cards")
                .select("*")
                .eq("shop_id", context["shop_id"])
                .eq("customer_phone", customer_phone)
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            ),
        )
    pending_cards = _merge_unique_rows(customer_cards, legacy_cards)
    events_by_order: Dict[str, List[Dict[str, Any]]] = {order_id: [] for order_id in order_ids}
    if order_ids:
        events = _safe_optional_query(
            "order_status_events",
            lambda: (
                supabase_client.table("order_status_events")
                .select("order_id, lifecycle_status, occurred_at")
                .eq("shop_id", context["shop_id"])
                .in_("order_id", order_ids)
                .order("occurred_at")
                .execute()
            ),
        )
        for event in events:
            events_by_order.setdefault(str(event["order_id"]), []).append(event)

    orders = []
    for order in order_rows:
        order_payload = dict(order)
        lifecycle_status = order_payload.get("lifecycle_status") or "received"
        order_number = order_payload.get("order_number")
        order_payload["source_id"] = str(order["id"])
        order_payload["display_reference"] = (
            str(order_number) if order_number is not None else str(order["id"])[-8:]
        )
        order_payload["record_type"] = "order"
        order_payload["items"] = items_by_order.get(str(order["id"]), [])
        order_payload["events"] = events_by_order.get(str(order["id"]), [])
        order_payload["lifecycle_status"] = lifecycle_status
        order_payload["updated_at"] = order_payload.get("updated_at") or order_payload["created_at"]
        order_payload["can_request_change"] = lifecycle_status in {
            "received", "pending_review", "approved"
        }
        order_payload["can_request_cancellation"] = lifecycle_status in {
            "received", "pending_review", "approved", "packing"
        }
        if lifecycle_status in {"packing", "out_for_delivery", "delivered", "cancelled"}:
            order_payload["restriction_reason"] = (
                "Items and delivery details are locked because packing has started. "
                "Contact the business if you still need help."
                if lifecycle_status == "packing"
                else "This order can no longer be changed. Contact the business if you need help."
            )
        for item_index, item in enumerate(order_payload["items"]):
            item["id"] = str(item.get("id") or f"{order['id']}:{item_index}")
            item["raw_name"] = item.get("raw_name") or item.get("display_name") or "Item"
        orders.append(CustomerPortalOrder(**order_payload))

    converted_action_card_ids = {
        str(order.get("action_card_id"))
        for order in order_rows
        if order.get("action_card_id")
    }
    for card in pending_cards:
        if str(card.get("id")) in converted_action_card_ids:
            continue
        card_status = str(card.get("status") or "pending").lower()
        if card_status not in {"pending", "approved"}:
            continue
        card_items = []
        total_amount = 0.0
        for index, item in enumerate(card.get("items") or []):
            quantity = _safe_float(item.get("quantity"))
            unit_price = _safe_float(item.get("price") or item.get("unit_price"))
            line_total = _safe_float(item.get("line_total"), quantity * unit_price)
            total_amount += line_total
            raw_name = item.get("raw_name") or item.get("name") or "Item"
            card_items.append(
                {
                    "id": f"{card['id']}:{index}",
                    "display_name": item.get("display_name") or item.get("name"),
                    "raw_name": raw_name,
                    "quantity": quantity,
                    "unit": item.get("unit"),
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )
        lifecycle_status = "approved" if card_status == "approved" else "received"
        events = [{
            "lifecycle_status": "received",
            "occurred_at": card["created_at"],
        }]
        if lifecycle_status == "approved":
            events.append({
                "lifecycle_status": "approved",
                "occurred_at": card.get("updated_at") or card["created_at"],
            })
        orders.append(
            CustomerPortalOrder(
                id=f"action-card:{card['id']}",
                source_id=str(card["id"]),
                display_reference=f"Draft {str(card['id']).removeprefix('ac_')[-8:]}",
                record_type="action_card",
                total_amount=total_amount,
                lifecycle_status=lifecycle_status,
                delivery_address=card.get("delivery_address"),
                delivery_time=(
                    card.get("delivery_time_normalized")
                    or card.get("delivery_time")
                    or card.get("delivery_time_raw")
                ),
                created_at=card["created_at"],
                updated_at=card.get("updated_at") or card["created_at"],
                revision=int(card.get("revision") or 1),
                can_edit=card_status == "pending" and not card.get("order_id"),
                restriction_reason=(
                    None
                    if card_status == "pending" and not card.get("order_id")
                    else "The owner has already approved this order, so direct editing is locked. Contact the business if you need help."
                ),
                items=card_items,
                events=events,
            )
        )

    orders.sort(key=lambda order: order.created_at, reverse=True)
    orders = orders[:50]
    return CustomerPortalOverview(
        customer_name=customer.get("name") or "Customer",
        shop_name=shop.get("name") or "Business",
        orders=orders,
    )


@router.patch("/action-cards/{action_card_id}")
def update_customer_action_card_draft(
    action_card_id: str,
    payload: CustomerDraftUpdate,
    context: Dict[str, Any] = Depends(get_customer_context),
):
    card = (
        supabase_client.table("action_cards")
        .select("id, shop_id, customer_id, order_id, status, revision")
        .eq("id", action_card_id)
        .eq("shop_id", context["shop_id"])
        .eq("customer_id", context["customer_id"])
        .execute()
    )
    if not card.data:
        raise HTTPException(status_code=404, detail="Pending order not found")
    current = card.data[0]
    if current.get("order_id") or current.get("status") != "pending":
        raise HTTPException(
            status_code=409,
            detail="This order has already moved into fulfilment and can no longer be edited",
        )

    try:
        items = normalize_amendment_items(context["shop_id"], payload.items)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        updated = supabase_client.rpc(
            "update_customer_action_card_draft",
            {
                "p_action_card_id": action_card_id,
                "p_shop_id": context["shop_id"],
                "p_customer_id": context["customer_id"],
                "p_expected_revision": payload.expected_revision,
                "p_items": items,
                "p_delivery_address": payload.delivery_address,
                "p_delivery_time": payload.delivery_time,
            },
        ).execute()
    except Exception as exc:
        error = str(exc).lower()
        if "revision_conflict" in error:
            raise HTTPException(
                status_code=409,
                detail="This order changed in another tab. Refresh and try again.",
            ) from exc
        if "not_editable" in error:
            raise HTTPException(
                status_code=409,
                detail="This order has already moved into fulfilment and can no longer be edited",
            ) from exc
        if "items_required" in error:
            raise HTTPException(
                status_code=422,
                detail="At least one valid item is required",
            ) from exc
        raise HTTPException(
            status_code=503,
            detail="Order editing is temporarily unavailable. Please try again.",
        ) from exc
    if not updated.data:
        raise HTTPException(status_code=409, detail="Order could not be updated")
    row = updated.data[0] if isinstance(updated.data, list) else updated.data
    return {
        "id": row["id"],
        "revision": row.get("revision", payload.expected_revision + 1),
        "status": row.get("status", "pending"),
        "message": "Order updated and sent to the owner for review.",
    }


@router.post("/orders/{order_id}/bill")
def create_portal_bill(
    order_id: str,
    context: Dict[str, Any] = Depends(get_customer_context),
):
    order = (
        supabase_client.table("orders")
        .select("id, shop_id")
        .eq("id", order_id)
        .eq("shop_id", context["shop_id"])
        .eq("customer_id", context["customer_id"])
        .execute()
    )
    if not order.data:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "bill_url": ensure_public_bill_link(
            order_id, context["shop_id"], db_client=supabase_client
        )
    }


@router.post("/orders/{order_id}/requests", status_code=201)
def create_order_request(
    order_id: str,
    payload: CustomerRequestCreate,
    context: Dict[str, Any] = Depends(get_customer_context),
):
    if payload.request_type == "support":
        raise HTTPException(status_code=400, detail="Use the support endpoint")
    if (
        payload.request_type == "change_order"
        and not (payload.message or "").strip()
        and payload.amendment is None
    ):
        raise HTTPException(status_code=422, detail="Describe the requested order change")
    order = (
        supabase_client.table("orders")
        .select("id, lifecycle_status")
        .eq("id", order_id)
        .eq("shop_id", context["shop_id"])
        .eq("customer_id", context["customer_id"])
        .execute()
    )
    if not order.data:
        raise HTTPException(status_code=404, detail="Order not found")
    lifecycle_status = order.data[0].get("lifecycle_status") or "received"
    if payload.request_type == "change_order" and lifecycle_status not in {
        "received", "pending_review", "approved"
    }:
        raise HTTPException(
            status_code=409,
            detail="Items and delivery details are locked because fulfilment has started",
        )
    if payload.request_type == "cancel_order" and lifecycle_status not in {
        "received", "pending_review", "approved", "packing"
    }:
        raise HTTPException(status_code=409, detail="This order can no longer be cancelled")

    request_payload = dict(payload.payload)
    if payload.amendment is not None:
        try:
            request_payload["proposed_amendment"] = {
                "items": normalize_amendment_items(
                    context["shop_id"], payload.amendment.items
                ),
                "delivery_address": payload.amendment.delivery_address,
                "delivery_time": payload.amendment.delivery_time,
            }
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _create_pending_order_request(
        context,
        order_id,
        payload.request_type,
        message=payload.message,
        payload=request_payload,
    )


@router.post("/support", status_code=201)
def create_support_request(
    payload: CustomerRequestCreate,
    context: Dict[str, Any] = Depends(get_customer_context),
):
    if payload.request_type != "support":
        raise HTTPException(status_code=400, detail="Invalid request type")
    if not (payload.message or "").strip():
        raise HTTPException(status_code=422, detail="Describe the problem")
    created = (
        supabase_client.table("customer_requests")
        .insert(
            {
                "shop_id": context["shop_id"],
                "customer_id": context["customer_id"],
                "request_type": "support",
                "message": payload.message.strip(),
                "payload": payload.payload,
            }
        )
        .execute()
    )
    if not created.data:
        raise HTTPException(status_code=500, detail="Failed to create support request")
    return created.data[0]


@router.post("/assistant", response_model=CustomerAssistantResponse)
async def customer_assistant(
    payload: CustomerAssistantRequest,
    context: Dict[str, Any] = Depends(get_customer_context),
):
    normalized = re.sub(r"\s+", " ", payload.message.strip().lower())
    repeat_requested = bool(re.search(
        r"\b(?:repeat|reorder|same order|order again|dobara|doobara|phir se|wahi order)\b|"
        r"(?:दोबारा|फिर से|वही ऑर्डर)",
        normalized,
    ))
    total_requested = bool(re.search(
        r"\b(?:order total|total amount|my total|kitna bana|kitne ka|amount)\b|"
        r"(?:कुल|टोटल|कितने का)",
        normalized,
    ))

    if repeat_requested:
        order = _latest_customer_order(context)
        if not order:
            return CustomerAssistantResponse(
                reply="Repeat karne ke liye koi previous order nahi mila.",
                intent=ConversationIntent.ORDER_UPDATE.value,
            )
        request = _create_pending_order_request(
            context,
            str(order["id"]),
            "repeat_order",
            message="Customer requested a repeat order through the portal assistant.",
        )
        return CustomerAssistantResponse(
            reply="Repeat order owner approval ke liye bhej diya gaya hai.",
            intent=ConversationIntent.ORDER_UPDATE.value,
            order_id=str(order["id"]),
            action="request_created" if not request.get("duplicate") else "request_pending",
        )

    if total_requested:
        order = _latest_customer_order(context)
        if not order:
            return CustomerAssistantResponse(
                reply="Aapke account mein total dikhane ke liye koi order nahi mila.",
                intent=ConversationIntent.PAYMENT_QUERY.value,
            )
        total = float(order.get("total_amount") or 0)
        status = str(order.get("lifecycle_status") or "received").replace("_", " ").title()
        return CustomerAssistantResponse(
            reply=f"Aapke latest order ka total ₹{total:.2f} hai. Status: {status}.",
            intent=ConversationIntent.PAYMENT_QUERY.value,
            order_id=str(order["id"]),
            action="view_order",
        )

    classification = IntentRouter.classify_intent_deterministically(payload.message)
    if classification is None:
        business_context = IntentRouter._get_business_context(context["shop_id"], {})
        try:
            raw = await asyncio.wait_for(
                GeminiService.classify_intent(payload.message, business_context),
                timeout=5,
            )
            classification = IntentClassification.model_validate(raw)
        except Exception:
            classification = IntentClassification(
                intent=ConversationIntent.UNCERTAIN, confidence=0.0, available=False
            )

    intent = classification.intent
    if intent == ConversationIntent.ORDER_TRACKING:
        order = _latest_customer_order(context)
        if not order:
            return CustomerAssistantResponse(
                reply="Aapke account mein abhi koi order nahi mila.",
                intent=intent.value,
            )
        status = str(order.get("lifecycle_status") or "received").replace("_", " ").title()
        return CustomerAssistantResponse(
            reply=f"Aapka latest order abhi {status} stage mein hai.",
            intent=intent.value,
            order_id=str(order["id"]),
            action="view_order",
        )

    if intent == ConversationIntent.PAYMENT_QUERY and IntentRouter._is_bill_request(payload.message):
        order = _latest_customer_order(context)
        if not order:
            return CustomerAssistantResponse(
                reply="Aapke account mein bill ke liye koi order nahi mila.",
                intent=intent.value,
            )
        bill_url = ensure_public_bill_link(
            str(order["id"]), context["shop_id"], db_client=supabase_client
        )
        return CustomerAssistantResponse(
            reply=f"Aapka latest bill yahan hai: {bill_url}",
            intent=intent.value,
            order_id=str(order["id"]),
            action="open_bill",
        )

    if intent == ConversationIntent.PRICE_ENQUIRY:
        catalog = (
            supabase_client.table("catalog_items")
            .select("display_name, canonical_name, base_price, unit, in_stock")
            .eq("shop_id", context["shop_id"])
            .eq("active", True)
            .limit(50)
            .execute()
        )
        words = {
            word for word in payload.message.lower().split()
            if len(word) > 2 and word not in {"price", "rate", "kya", "hai", "kitna", "what"}
        }
        matches = [
            item for item in catalog.data or []
            if any(word in f"{item.get('display_name', '')} {item.get('canonical_name', '')}".lower() for word in words)
        ][:5]
        if matches:
            lines = [
                f"{item.get('display_name') or item.get('canonical_name')}: ₹{float(item.get('base_price') or 0):.2f}/{item.get('unit') or 'unit'}"
                for item in matches
            ]
            return CustomerAssistantResponse(reply="\n".join(lines), intent=intent.value)

    if intent == ConversationIntent.ORDER_CANCEL:
        return CustomerAssistantResponse(
            reply="Order card par 'Request cancellation' use karein. Owner approval ke baad status update hoga.",
            intent=intent.value,
            action="request_cancellation",
        )

    return CustomerAssistantResponse(
        reply=(
            "Main order status, bill aur catalog price mein help kar sakta hoon. "
            "Order change ya complaint owner approval ke liye request ke roop mein bheji jayegi."
        ),
        intent=intent.value,
    )
