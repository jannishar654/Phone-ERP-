from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes.customer import get_customer_context
from app.dependencies.auth import get_current_user_id
from app.services.customer_portal_service import (
    create_customer_portal_magic_link,
    exchange_magic_link,
    validate_customer_session,
)
from app.utils.security import hash_token


class Result:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.operation = "select"
        self.payload = None
        self.filters = []

    def select(self, *_args):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def neq(self, field, value):
        self.filters.append(("neq", field, value))
        return self

    def is_(self, field, value):
        self.filters.append(("is", field, value))
        return self

    def in_(self, field, value):
        self.filters.append(("in", field, value))
        return self

    def lte(self, field, value):
        self.filters.append(("lte", field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        self.db.calls.append(self)
        key = (self.table, self.operation)
        queue = self.db.responses.get(key, [])
        value = queue.pop(0) if queue else []
        if isinstance(value, Exception):
            raise value
        return Result(value)


class FakeDb:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def table(self, name):
        return FakeQuery(self, name)

    def rpc(self, name, payload):
        query = FakeQuery(self, f"rpc:{name}")
        query.operation = "rpc"
        query.payload = payload
        return query


def future(hours=1):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_customer_access_link_is_stable_and_stores_hash_only():
    db = FakeDb(
        {
            ("rpc:issue_customer_portal_magic_link", "rpc"): [["new-link"]],
        }
    )
    with patch(
        "app.services.customer_portal_service.generate_deterministic_customer_portal_token",
        return_value="private-raw-token",
    ):
        first_url = create_customer_portal_magic_link(
            "shop-1", "customer-1", "whatsapp", db_client=db
        )

    issue = db.calls[0]
    assert issue.payload["p_token_hash"] == hash_token("private-raw-token")
    assert issue.payload["p_shop_id"] == "shop-1"
    assert issue.payload["p_customer_id"] == "customer-1"
    assert "private-raw-token" not in str(issue.payload)
    assert first_url.endswith("/customer/access#token=private-raw-token")


def test_customer_access_link_regenerates_the_same_customer_url():
    db = FakeDb(
        {
            ("rpc:issue_customer_portal_magic_link", "rpc"): [
                ["access-link"],
                ["access-link"],
            ],
        }
    )
    with patch(
        "app.services.customer_portal_service.generate_deterministic_customer_portal_token",
        return_value="stable-customer-token",
    ):
        first_url = create_customer_portal_magic_link(
            "shop-1", "customer-1", "whatsapp", db_client=db
        )
        second_url = create_customer_portal_magic_link(
            "shop-1", "customer-1", "whatsapp", db_client=db
        )

    assert first_url == second_url
    assert len(db.calls) == 2


def test_customer_access_exchanges_for_hashed_session():
    db = FakeDb(
        {
            ("rpc:exchange_customer_portal_magic_link", "rpc"): [[{
                "shop_id": "shop-1",
                "customer_id": "customer-1",
            }]],
        }
    )
    with patch(
        "app.services.customer_portal_service.secrets.token_urlsafe",
        return_value="raw-session-token",
    ):
        result = exchange_magic_link("raw-magic-token", db_client=db)

    exchange = db.calls[0]
    assert result["session_token"] == "raw-session-token"
    assert exchange.payload["p_token_hash"] == hash_token("raw-magic-token")
    assert exchange.payload["p_session_hash"] == hash_token("raw-session-token")
    assert "raw-session-token" not in str(exchange.payload)


def test_expired_magic_link_is_rejected_without_creating_session():
    db = FakeDb(
        {
            ("rpc:exchange_customer_portal_magic_link", "rpc"): [
                RuntimeError("link_expired")
            ],
        }
    )
    with pytest.raises(ValueError, match="link_expired"):
        exchange_magic_link("expired-token", db_client=db)
    assert len(db.calls) == 1


def test_exchange_infrastructure_failure_returns_safe_service_unavailable():
    with patch(
        "app.routes.customer.exchange_magic_link",
        side_effect=RuntimeError("database details must not leak"),
    ):
        response = client.post(
            "/customer/access/exchange",
            json={"token": "a-valid-length-customer-magic-token"},
            headers={"Origin": "https://phone-erp.vercel.app"},
        )

    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == "https://phone-erp.vercel.app"
    assert response.json()["detail"] == (
        "Customer portal is temporarily unavailable. Please try again shortly."
    )


def test_customer_session_validation_is_scoped_and_updates_last_used():
    db = FakeDb(
        {
            ("customer_portal_sessions", "select"): [[{
                "id": "session-1",
                "shop_id": "shop-1",
                "customer_id": "customer-1",
                "expires_at": future(),
                "revoked_at": None,
            }]],
            ("customer_portal_sessions", "update"): [[{"id": "session-1"}]],
        }
    )
    result = validate_customer_session("raw-session", db_client=db)
    select = db.calls[0]
    assert ("eq", "token_hash", hash_token("raw-session")) in select.filters
    assert result["shop_id"] == "shop-1"
    assert result["customer_id"] == "customer-1"


client = TestClient(app)


@pytest.fixture
def portal_context():
    context = {
        "id": "session-1",
        "shop_id": "shop-1",
        "customer_id": "customer-1",
        "expires_at": future(),
    }
    app.dependency_overrides[get_customer_context] = lambda: context
    yield context
    app.dependency_overrides.pop(get_customer_context, None)


def test_customer_orders_are_filtered_by_both_shop_and_customer(portal_context):
    db = FakeDb(
        {
            ("customers", "select"): [[{
                "id": "customer-1", "shop_id": "shop-1", "name": "Danish", "phone": "+911234567890"
            }]],
            ("shops", "select"): [[{"id": "shop-1", "name": "Test Shop"}]],
            ("orders", "select"): [[{
                "id": "order-1",
                "order_number": 101,
                "total_amount": 675.0,
                "lifecycle_status": "packing",
                "delivery_address": "Batla House",
                "delivery_time": None,
                "created_at": "2026-07-16T10:00:00+00:00",
                "updated_at": "2026-07-16T10:05:00+00:00",
                "packed_at": "2026-07-16T10:05:00+00:00",
                "out_for_delivery_at": None,
                "delivered_at": None,
                "cancelled_at": None,
                "order_items": [],
            }]],
            ("order_status_events", "select"): [[]],
        }
    )
    with patch("app.routes.customer.supabase_client", db):
        response = client.get("/customer/orders")
    assert response.status_code == 200
    order_query = next(call for call in db.calls if call.table == "orders")
    assert ("eq", "shop_id", "shop-1") in order_query.filters
    assert ("eq", "customer_id", "customer-1") in order_query.filters
    assert response.json()["orders"][0]["id"] == "order-1"


def test_pending_action_card_appears_as_received_for_same_customer(portal_context):
    db = FakeDb(
        {
            ("customers", "select"): [[{
                "id": "customer-1", "shop_id": "shop-1", "name": "Danish", "phone": "+911234567890"
            }]],
            ("shops", "select"): [[{"id": "shop-1", "name": "Test Shop"}]],
            ("orders", "select"): [[]],
            ("action_cards", "select"): [[{
                "id": "ac-1",
                "status": "pending",
                "items": [{"name": "Aata", "raw_name": "aata", "quantity": 5, "unit": "kg", "price": 45}],
                "delivery_address": "Batla House",
                "delivery_time": "2026-07-28 5:30 PM",
                "delivery_time_normalized": "2026-07-28 5:30 PM",
                "created_at": "2026-07-16T10:00:00+00:00",
                "updated_at": "2026-07-16T10:00:00+00:00",
            }]],
        }
    )
    with patch("app.routes.customer.supabase_client", db):
        response = client.get("/customer/orders")

    assert response.status_code == 200
    order = response.json()["orders"][0]
    assert order["record_type"] == "action_card"
    assert order["lifecycle_status"] == "received"
    assert order["total_amount"] == 225.0
    assert order["source_id"] == "ac-1"
    assert order["display_reference"] == "Draft ac-1"
    assert order["can_edit"] is True
    assert order["revision"] == 1
    assert order["delivery_time"] == "2026-07-28 5:30 PM"
    card_query = next(call for call in db.calls if call.table == "action_cards")
    assert ("eq", "shop_id", "shop-1") in card_query.filters
    assert ("eq", "customer_id", "customer-1") in card_query.filters


def test_customer_edits_pending_draft_with_server_resolved_prices(portal_context):
    normalized_items = [{
        "name": "Aashirvaad Atta",
        "raw_name": "aata",
        "quantity": 10.0,
        "unit": "kg",
        "price": 45.0,
        "resolution_status": "matched",
    }]
    db = FakeDb({
        ("action_cards", "select"): [[{
            "id": "ac-1",
            "shop_id": "shop-1",
            "customer_id": "customer-1",
            "order_id": None,
            "status": "pending",
            "revision": 2,
        }]],
        ("rpc:update_customer_action_card_draft", "rpc"): [[{
            "id": "ac-1", "status": "pending", "revision": 3,
        }]],
    })
    with patch("app.routes.customer.supabase_client", db), patch(
        "app.routes.customer.normalize_amendment_items",
        return_value=normalized_items,
    ) as normalize:
        response = client.patch(
            "/customer/action-cards/ac-1",
            json={
                "expected_revision": 2,
                "items": [{"name": "aata", "quantity": 10, "unit": "kg"}],
                "delivery_address": "Batla House",
                "delivery_time": "Tomorrow 9:30 PM",
            },
        )

    assert response.status_code == 200
    assert response.json()["revision"] == 3
    normalize.assert_called_once()
    card_query = db.calls[0]
    assert ("eq", "shop_id", "shop-1") in card_query.filters
    assert ("eq", "customer_id", "customer-1") in card_query.filters
    rpc = next(call for call in db.calls if call.operation == "rpc")
    assert rpc.payload["p_expected_revision"] == 2
    assert rpc.payload["p_items"] == normalized_items
    assert "price" not in response.request.content.decode()


def test_customer_cannot_edit_another_customers_draft(portal_context):
    db = FakeDb({("action_cards", "select"): [[]]})
    with patch("app.routes.customer.supabase_client", db):
        response = client.patch(
            "/customer/action-cards/other-card",
            json={
                "expected_revision": 1,
                "items": [{"name": "aata", "quantity": 5, "unit": "kg"}],
            },
        )

    assert response.status_code == 404
    query = db.calls[0]
    assert ("eq", "shop_id", "shop-1") in query.filters
    assert ("eq", "customer_id", "customer-1") in query.filters


def test_stale_customer_draft_edit_returns_conflict(portal_context):
    db = FakeDb({
        ("action_cards", "select"): [[{
            "id": "ac-1",
            "shop_id": "shop-1",
            "customer_id": "customer-1",
            "order_id": None,
            "status": "pending",
            "revision": 3,
        }]],
        ("rpc:update_customer_action_card_draft", "rpc"): [
            RuntimeError("action_card_revision_conflict")
        ],
    })
    with patch("app.routes.customer.supabase_client", db), patch(
        "app.routes.customer.normalize_amendment_items",
        return_value=[{"name": "Aata", "quantity": 5, "price": 45}],
    ):
        response = client.patch(
            "/customer/action-cards/ac-1",
            json={
                "expected_revision": 2,
                "items": [{"name": "aata", "quantity": 5, "unit": "kg"}],
            },
        )

    assert response.status_code == 409
    assert "another tab" in response.json()["detail"]


def test_converted_customer_draft_cannot_be_edited(portal_context):
    db = FakeDb({
        ("action_cards", "select"): [[{
            "id": "ac-1",
            "shop_id": "shop-1",
            "customer_id": "customer-1",
            "order_id": "order-1",
            "status": "converted",
            "revision": 1,
        }]],
    })
    with patch("app.routes.customer.supabase_client", db):
        response = client.patch(
            "/customer/action-cards/ac-1",
            json={
                "expected_revision": 1,
                "items": [{"name": "aata", "quantity": 5, "unit": "kg"}],
            },
        )

    assert response.status_code == 409
    assert not any(call.operation == "rpc" for call in db.calls)


def test_approved_customer_draft_cannot_be_changed_directly(portal_context):
    db = FakeDb({
        ("action_cards", "select"): [[{
            "id": "ac-1",
            "shop_id": "shop-1",
            "customer_id": "customer-1",
            "order_id": None,
            "status": "approved",
            "revision": 1,
        }]],
    })
    with patch("app.routes.customer.supabase_client", db):
        response = client.patch(
            "/customer/action-cards/ac-1",
            json={
                "expected_revision": 1,
                "items": [{"name": "aata", "quantity": 5, "unit": "kg"}],
            },
        )

    assert response.status_code == 409
    assert not any(call.operation == "rpc" for call in db.calls)


def test_optional_portal_history_failure_does_not_hide_orders(portal_context):
    db = FakeDb(
        {
            ("customers", "select"): [[{
                "id": "customer-1", "shop_id": "shop-1", "name": "Danish", "phone": "+911234567890"
            }]],
            ("shops", "select"): [[{"id": "shop-1", "name": "Test Shop"}]],
            ("orders", "select"): [[{
                "id": "order-1",
                "total_amount": 225,
                "lifecycle_status": "packing",
                "created_at": "2026-07-16T10:00:00+00:00",
                "updated_at": "2026-07-16T10:00:00+00:00",
            }]],
            ("order_items", "select"): [[{
                "id": "item-1", "order_id": "order-1", "raw_name": "aata",
                "quantity": 5, "unit": "kg", "unit_price": 45, "line_total": 225,
            }]],
            ("action_cards", "select"): [RuntimeError("optional table unavailable")],
            ("order_status_events", "select"): [RuntimeError("optional table unavailable")],
        }
    )
    with patch("app.routes.customer.supabase_client", db):
        response = client.get("/customer/orders")

    assert response.status_code == 200
    assert response.json()["orders"][0]["id"] == "order-1"


def test_legacy_phone_linked_action_card_appears_in_customer_portal(portal_context):
    db = FakeDb(
        {
            ("customers", "select"): [[{
                "id": "customer-1", "shop_id": "shop-1", "name": "Danish",
                "phone": "+911234567890",
            }]],
            ("shops", "select"): [[{"id": "shop-1", "name": "Test Shop"}]],
            ("orders", "select"): [[], []],
            ("action_cards", "select"): [[], [{
                "id": "legacy-card-1",
                "shop_id": "shop-1",
                "customer_id": None,
                "customer_phone": "+911234567890",
                "status": "pending",
                "items": [{"name": "Aata", "quantity": 5, "unit": "kg", "price": 45}],
                "created_at": "2026-07-16T10:00:00+00:00",
                "updated_at": "2026-07-16T10:00:00+00:00",
            }]],
        }
    )
    with patch("app.routes.customer.supabase_client", db):
        response = client.get("/customer/orders")

    assert response.status_code == 200
    assert response.json()["orders"][0]["id"] == "action-card:legacy-card-1"
    assert response.json()["orders"][0]["lifecycle_status"] == "received"
    legacy_order_query = [
        call
        for call in db.calls
        if call.table == "orders"
        and ("eq", "customer_phone", "+911234567890") in call.filters
    ][0]
    legacy_card_query = [
        call
        for call in db.calls
        if call.table == "action_cards"
        and ("eq", "customer_phone", "+911234567890") in call.filters
    ][0]
    assert ("is", "customer_id", "null") in legacy_order_query.filters
    assert ("is", "customer_id", "null") in legacy_card_query.filters


def test_action_card_controller_persists_customer_id():
    from app.controllers.action_card import ActionCardController

    created_row = {
        "id": "card-1",
        "shop_id": "shop-1",
        "customer_id": "customer-1",
        "source": "whatsapp",
        "message_type": "ORDER",
        "transcript": "5 kg aata",
        "items": [],
        "status": "pending",
        "created_at": "2026-07-16T10:00:00+00:00",
    }
    with patch("app.controllers.action_card.SupabaseService.is_available", return_value=True), patch(
        "app.controllers.action_card.SupabaseService.create", return_value=created_row
    ) as create:
        ActionCardController.create_card(
            {
                **created_row,
                "customer_id": "customer-1",
            }
        )

    assert create.call_args.args[0]["customer_id"] == "customer-1"


def test_customer_portal_unhandled_failure_is_cors_safe(portal_context):
    db = FakeDb({("customers", "select"): [RuntimeError("database unavailable")]})
    with patch("app.routes.customer.supabase_client", db):
        response = client.get(
            "/customer/orders",
            headers={"Origin": "https://phone-erp.vercel.app"},
        )

    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == "https://phone-erp.vercel.app"
    assert response.json()["request_id"]


def test_owner_customer_requests_are_enriched_without_embedded_relationships():
    request = {
        "id": "request-1",
        "shop_id": "shop-1",
        "customer_id": "customer-1",
        "order_id": "order-1",
        "request_type": "cancel_order",
        "status": "pending",
        "created_at": "2026-07-17T10:00:00+00:00",
    }
    db = FakeDb({
        ("customer_requests", "select"): [[request]],
        ("customers", "select"): [[{
            "id": "customer-1", "name": "Danish", "phone": "+911234567890"
        }]],
        ("orders", "select"): [[{
            "id": "order-1",
            "order_number": 101,
            "lifecycle_status": "packing",
            "total_amount": 500,
        }]],
    })
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    try:
        with patch("app.routes.customer_requests.supabase_client", db), patch(
            "app.routes.customer_requests.get_user_shop_id", return_value="shop-1"
        ):
            response = client.get("/customer-requests?status=pending")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    assert response.json()[0]["customers"]["name"] == "Danish"
    assert response.json()[0]["orders"]["lifecycle_status"] == "packing"
    request_query, customer_query, order_query = db.calls
    assert request_query.filters == [
        ("eq", "shop_id", "shop-1"),
        ("eq", "status", "pending"),
    ]
    assert ("eq", "shop_id", "shop-1") in customer_query.filters
    assert ("in", "id", ["customer-1"]) in customer_query.filters
    assert ("eq", "shop_id", "shop-1") in order_query.filters
    assert ("in", "id", ["order-1"]) in order_query.filters


def test_owner_customer_requests_tolerate_missing_related_records():
    request = {
        "id": "request-2",
        "shop_id": "shop-1",
        "customer_id": "deleted-customer",
        "order_id": None,
        "request_type": "support",
        "status": "pending",
        "created_at": "2026-07-17T10:00:00+00:00",
    }
    db = FakeDb({
        ("customer_requests", "select"): [[request]],
        ("customers", "select"): [[]],
    })
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    try:
        with patch("app.routes.customer_requests.supabase_client", db), patch(
            "app.routes.customer_requests.get_user_shop_id", return_value="shop-1"
        ):
            response = client.get("/customer-requests?status=pending")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    assert response.json()[0]["customers"] is None
    assert response.json()[0]["orders"] is None


def test_owner_customer_requests_survive_enrichment_failures():
    request = {
        "id": "request-3",
        "shop_id": "shop-1",
        "customer_id": "customer-1",
        "order_id": "order-1",
        "request_type": "change_order",
        "status": "pending",
        "created_at": "2026-07-18T10:00:00+00:00",
    }
    db = FakeDb({
        ("customer_requests", "select"): [[request]],
        ("customers", "select"): [RuntimeError("customer enrichment unavailable")],
        ("orders", "select"): [
            RuntimeError("order_number is unavailable"),
            RuntimeError("order enrichment unavailable"),
        ],
    })
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    try:
        with patch("app.routes.customer_requests.supabase_client", db), patch(
            "app.routes.customer_requests.get_user_shop_id", return_value="shop-1"
        ):
            response = client.get("/customer-requests?status=pending")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    assert response.json()[0]["id"] == "request-3"
    assert response.json()[0]["customers"] is None
    assert response.json()[0]["orders"] is None


def test_customer_cannot_open_bill_for_another_customer(portal_context):
    db = FakeDb({("orders", "select"): [[]]})
    with patch("app.routes.customer.supabase_client", db):
        response = client.post("/customer/orders/other-order/bill")
    assert response.status_code == 404
    query = db.calls[0]
    assert ("eq", "shop_id", "shop-1") in query.filters
    assert ("eq", "customer_id", "customer-1") in query.filters


def test_customer_request_is_idempotent_while_pending(portal_context):
    db = FakeDb(
        {
            ("orders", "select"): [[{"id": "order-1", "lifecycle_status": "packing"}]],
            ("customer_requests", "select"): [[{"id": "request-1"}]],
        }
    )
    with patch("app.routes.customer.supabase_client", db):
        response = client.post(
            "/customer/orders/order-1/requests",
            json={"request_type": "cancel_order", "payload": {}},
        )
    assert response.status_code == 201
    assert response.json() == {"id": "request-1", "status": "pending", "duplicate": True}
    assert not any(
        call.table == "customer_requests" and call.operation == "insert"
        for call in db.calls
    )


def test_change_request_requires_customer_instructions(portal_context):
    db = FakeDb()
    with patch("app.routes.customer.supabase_client", db):
        response = client.post(
            "/customer/orders/order-1/requests",
            json={"request_type": "change_order", "message": "", "payload": {}},
        )
    assert response.status_code == 422
    assert not db.calls


def test_customer_change_request_is_locked_after_packing_starts(portal_context):
    db = FakeDb({
        ("orders", "select"): [[{
            "id": "order-1", "lifecycle_status": "packing",
        }]],
    })
    with patch("app.routes.customer.supabase_client", db), patch(
        "app.routes.customer.normalize_amendment_items"
    ) as normalize:
        response = client.post(
            "/customer/orders/order-1/requests",
            json={
                "request_type": "change_order",
                "payload": {},
                "amendment": {
                    "items": [{"name": "aata", "quantity": 5, "unit": "kg"}],
                },
            },
        )

    assert response.status_code == 409
    normalize.assert_not_called()


def test_customer_cancellation_is_locked_after_dispatch(portal_context):
    db = FakeDb({
        ("orders", "select"): [[{
            "id": "order-1", "lifecycle_status": "out_for_delivery",
        }]],
    })
    with patch("app.routes.customer.supabase_client", db):
        response = client.post(
            "/customer/orders/order-1/requests",
            json={"request_type": "cancel_order", "payload": {}},
        )

    assert response.status_code == 409


def test_structured_change_request_stores_server_normalized_amendment(portal_context):
    normalized_items = [{
        "name": "Aashirvaad Atta",
        "raw_name": "aata",
        "quantity": 10.0,
        "unit": "kg",
        "price": 45.0,
        "resolution_status": "matched",
    }]
    db = FakeDb({
        ("orders", "select"): [[{
            "id": "order-1", "lifecycle_status": "approved",
        }]],
        ("customer_requests", "select"): [[]],
        ("customer_requests", "insert"): [[{
            "id": "request-1", "status": "pending",
        }]],
        ("owner_notifications", "insert"): [[{"id": "notification-1"}]],
    })
    with patch("app.routes.customer.supabase_client", db), patch(
        "app.routes.customer.normalize_amendment_items",
        return_value=normalized_items,
    ):
        response = client.post(
            "/customer/orders/order-1/requests",
            json={
                "request_type": "change_order",
                "payload": {},
                "amendment": {
                    "items": [{"name": "aata", "quantity": 10, "unit": "kg"}],
                    "delivery_address": "New address",
                    "delivery_time": "Tomorrow 8 PM",
                },
            },
        )

    assert response.status_code == 201
    request_insert = next(
        call for call in db.calls
        if call.table == "customer_requests" and call.operation == "insert"
    )
    proposed = request_insert.payload["payload"]["proposed_amendment"]
    assert proposed["items"] == normalized_items
    assert proposed["delivery_address"] == "New address"
    assert proposed["delivery_time"] == "Tomorrow 8 PM"


def test_latest_change_replaces_an_earlier_pending_change(portal_context):
    normalized_items = [{
        "name": "Aashirvaad Atta", "quantity": 12, "unit": "kg", "price": 45,
    }]
    db = FakeDb({
        ("orders", "select"): [[{
            "id": "order-1", "lifecycle_status": "approved",
        }]],
        ("customer_requests", "select"): [[{
            "id": "request-1", "status": "pending",
        }]],
        ("customer_requests", "update"): [[{
            "id": "request-1", "status": "pending",
        }]],
    })
    with patch("app.routes.customer.supabase_client", db), patch(
        "app.routes.customer.normalize_amendment_items",
        return_value=normalized_items,
    ):
        response = client.post(
            "/customer/orders/order-1/requests",
            json={
                "request_type": "change_order",
                "payload": {},
                "amendment": {
                    "items": [{"name": "aata", "quantity": 12, "unit": "kg"}],
                    "delivery_address": "Latest address",
                },
            },
        )

    assert response.status_code == 201
    assert response.json()["updated"] is True
    update = next(
        call for call in db.calls
        if call.table == "customer_requests" and call.operation == "update"
    )
    assert ("eq", "status", "pending") in update.filters
    assert update.payload["payload"]["proposed_amendment"]["items"] == normalized_items
    assert update.payload["payload"]["proposed_amendment"]["delivery_address"] == "Latest address"


def test_change_is_rejected_once_owner_has_claimed_previous_request(portal_context):
    db = FakeDb({
        ("orders", "select"): [[{
            "id": "order-1", "lifecycle_status": "approved",
        }]],
        ("customer_requests", "select"): [[{
            "id": "request-1", "status": "processing",
        }]],
    })
    with patch("app.routes.customer.supabase_client", db), patch(
        "app.routes.customer.normalize_amendment_items",
        return_value=[{"name": "Aata", "quantity": 12, "price": 45}],
    ):
        response = client.post(
            "/customer/orders/order-1/requests",
            json={
                "request_type": "change_order",
                "payload": {},
                "amendment": {
                    "items": [{"name": "aata", "quantity": 12, "unit": "kg"}],
                },
            },
        )

    assert response.status_code == 409
    assert "already reviewing" in response.json()["detail"]


def test_support_request_requires_message(portal_context):
    db = FakeDb()
    with patch("app.routes.customer.supabase_client", db):
        response = client.post(
            "/customer/support",
            json={"request_type": "support", "message": "   ", "payload": {}},
        )
    assert response.status_code == 422
    assert not db.calls


def test_owner_repeat_approval_claims_request_and_creates_one_review_card():
    request = {
        "id": "request-1",
        "shop_id": "shop-1",
        "customer_id": "customer-1",
        "order_id": "order-1",
        "request_type": "repeat_order",
        "status": "pending",
        "payload": {},
    }
    db = FakeDb(
        {
            ("customer_requests", "select"): [[request]],
            ("customer_requests", "update"): [
                [{**request, "status": "processing"}],
                [{**request, "status": "approved", "payload": {"action_card_id": "ac-repeat"}}],
            ],
            ("action_cards", "select"): [[]],
            ("orders", "select"): [[{
                "id": "order-1",
                "shop_id": "shop-1",
                "customer_id": "customer-1",
                "customer_name": "Danish",
                "customer_phone": "+911234567890",
                "delivery_address": "Batla House",
                "order_items": [{
                    "raw_name": "aata",
                    "display_name": "Aashirvaad Atta",
                    "quantity": 5,
                    "unit": "kg",
                    "unit_price": 45,
                    "catalog_item_id": "catalog-1",
                }],
            }]],
            ("customers", "select"): [[{
                "name": "Danish", "phone": "+911234567890", "address": "Batla House"
            }]],
            ("action_cards", "insert"): [[{"id": "ac-repeat"}]],
        }
    )
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    try:
        with patch("app.routes.customer_requests.supabase_client", db), patch(
            "app.routes.customer_requests.get_user_shop_id", return_value="shop-1"
        ):
            response = client.patch(
                "/customer-requests/request-1",
                json={"status": "approved"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    card_insert = next(
        call for call in db.calls
        if call.table == "action_cards" and call.operation == "insert"
    )
    assert card_insert.payload["customer_request_id"] == "request-1"
    request_updates = [
        call for call in db.calls
        if call.table == "customer_requests" and call.operation == "update"
    ]
    assert ("eq", "status", "pending") in request_updates[0].filters
    assert ("eq", "status", "processing") in request_updates[1].filters


def test_owner_review_card_uses_customer_proposed_amendment():
    from app.routes.customer_requests import _create_review_action_card

    proposed_items = [{
        "name": "Aashirvaad Atta",
        "raw_name": "aata",
        "quantity": 10,
        "unit": "kg",
        "price": 45,
        "resolution_status": "matched",
    }]
    request = {
        "id": "request-change-1",
        "shop_id": "shop-1",
        "customer_id": "customer-1",
        "order_id": "order-1",
        "request_type": "change_order",
        "status": "processing",
        "message": "Please update my order",
        "payload": {
            "proposed_amendment": {
                "items": proposed_items,
                "delivery_address": "New address",
                "delivery_time": "Tomorrow 8 PM",
            }
        },
    }
    db = FakeDb({
        ("action_cards", "select"): [[]],
        ("orders", "select"): [[{
            "id": "order-1",
            "customer_name": "Danish",
            "customer_phone": "+911234567890",
            "delivery_address": "Old address",
            "delivery_time": "Tomorrow 9 PM",
            "order_items": [{
                "raw_name": "sugar", "quantity": 5, "unit": "kg", "unit_price": 45,
            }],
        }]],
        ("customers", "select"): [[{
            "name": "Danish", "phone": "+911234567890", "address": "Old address",
        }]],
        ("action_cards", "insert"): [[{"id": "ac-change"}]],
    })
    with patch("app.routes.customer_requests.supabase_client", db):
        card_id = _create_review_action_card(request, "owner-1")

    assert card_id.startswith("ac_change_")
    card_insert = next(
        call for call in db.calls
        if call.table == "action_cards" and call.operation == "insert"
    )
    assert card_insert.payload["items"] == proposed_items
    assert card_insert.payload["delivery_address"] == "New address"
    assert card_insert.payload["delivery_time"] == "Tomorrow 8 PM"


def test_owner_cancellation_uses_atomic_shop_scoped_database_function():
    request = {
        "id": "request-2",
        "shop_id": "shop-1",
        "customer_id": "customer-1",
        "order_id": "order-2",
        "request_type": "cancel_order",
        "status": "pending",
        "payload": {},
    }
    db = FakeDb(
        {
            ("customer_requests", "select"): [[request]],
            ("rpc:approve_customer_cancellation", "rpc"): [[{
                **request, "status": "approved"
            }]],
        }
    )
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    try:
        with patch("app.routes.customer_requests.supabase_client", db), patch(
            "app.routes.customer_requests.get_user_shop_id", return_value="shop-1"
        ):
            response = client.patch(
                "/customer-requests/request-2",
                json={"status": "approved", "owner_note": "Approved"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    rpc = next(call for call in db.calls if call.operation == "rpc")
    assert rpc.payload == {
        "p_request_id": "request-2",
        "p_shop_id": "shop-1",
        "p_owner_note": "Approved",
    }


@pytest.mark.parametrize(
    ("request_type", "decision"),
    [("support", "approved"), ("repeat_order", "resolved")],
)
def test_owner_rejects_invalid_request_decision_for_type(request_type, decision):
    request = {
        "id": "request-invalid-decision",
        "shop_id": "shop-1",
        "customer_id": "customer-1",
        "order_id": None if request_type == "support" else "order-1",
        "request_type": request_type,
        "status": "pending",
        "payload": {},
    }
    db = FakeDb({("customer_requests", "select"): [[request]]})
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    try:
        with patch("app.routes.customer_requests.supabase_client", db), patch(
            "app.routes.customer_requests.get_user_shop_id", return_value="shop-1"
        ):
            response = client.patch(
                "/customer-requests/request-invalid-decision",
                json={"status": decision},
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 422
    assert not any(
        call.table == "customer_requests" and call.operation == "update"
        for call in db.calls
    )


def test_owner_notifications_are_due_and_shop_scoped():
    db = FakeDb(
        {
            ("owner_notifications", "select"): [[{
                "id": "notification-1",
                "notification_type": "order_reminder",
                "title": "Order still waiting",
                "message": "Review the order",
                "scheduled_at": "2026-07-16T10:00:00+00:00",
                "action_card_id": "ac-1",
                "customer_request_id": None,
            }]],
        }
    )
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    try:
        with patch("app.routes.owner_notifications.supabase_client", db), patch(
            "app.routes.owner_notifications.get_user_shop_id", return_value="shop-1"
        ):
            response = client.get("/owner-notifications")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    query = db.calls[0]
    assert ("eq", "shop_id", "shop-1") in query.filters
    assert any(item[0] == "lte" and item[1] == "scheduled_at" for item in query.filters)


def test_owner_notification_acknowledgement_is_shop_scoped():
    notification = {
        "id": "notification-1",
        "notification_type": "new_order",
        "title": "New customer order",
        "message": "Review the order",
        "scheduled_at": "2026-07-16T10:00:00+00:00",
        "action_card_id": "ac-1",
        "customer_request_id": None,
    }
    db = FakeDb({("owner_notifications", "update"): [[notification]]})
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    try:
        with patch("app.routes.owner_notifications.supabase_client", db), patch(
            "app.routes.owner_notifications.get_user_shop_id", return_value="shop-1"
        ):
            response = client.post("/owner-notifications/notification-1/ack")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 200
    update = db.calls[0]
    assert ("eq", "id", "notification-1") in update.filters
    assert ("eq", "shop_id", "shop-1") in update.filters


def test_owner_cannot_acknowledge_another_shops_notification():
    db = FakeDb(
        {
            ("owner_notifications", "update"): [[]],
            ("owner_notifications", "select"): [[]],
        }
    )
    app.dependency_overrides[get_current_user_id] = lambda: "owner-1"
    try:
        with patch("app.routes.owner_notifications.supabase_client", db), patch(
            "app.routes.owner_notifications.get_user_shop_id", return_value="shop-1"
        ):
            response = client.post("/owner-notifications/other-shop-alert/ack")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert response.status_code == 404
    assert all(("eq", "shop_id", "shop-1") in call.filters for call in db.calls)


def test_customer_assistant_prepares_repeat_request_with_owner_approval(portal_context):
    db = FakeDb(
        {
            ("orders", "select"): [[{
                "id": "order-1",
                "order_number": 101,
                "total_amount": 675,
                "lifecycle_status": "delivered",
                "created_at": "2026-07-16T10:00:00+00:00",
            }]],
            ("customer_requests", "select"): [[]],
            ("customer_requests", "insert"): [[{
                "id": "request-1", "status": "pending"
            }]],
        }
    )
    with patch("app.routes.customer.supabase_client", db):
        response = client.post(
            "/customer/assistant",
            json={"message": "Please repeat my same order again"},
        )

    assert response.status_code == 200
    assert response.json()["action"] == "request_created"
    request_insert = next(
        call for call in db.calls
        if call.table == "customer_requests" and call.operation == "insert"
    )
    assert request_insert.payload["request_type"] == "repeat_order"
    assert request_insert.payload["shop_id"] == "shop-1"
    assert request_insert.payload["customer_id"] == "customer-1"


def test_customer_assistant_explains_total_from_database(portal_context):
    db = FakeDb(
        {
            ("orders", "select"): [[{
                "id": "order-1",
                "order_number": 101,
                "total_amount": 6920,
                "lifecycle_status": "packing",
                "created_at": "2026-07-16T10:00:00+00:00",
            }]],
        }
    )
    with patch("app.routes.customer.supabase_client", db):
        response = client.post(
            "/customer/assistant",
            json={"message": "Mera order total kitna bana?"},
        )

    assert response.status_code == 200
    assert "₹6920.00" in response.json()["reply"]
    assert "Packing" in response.json()["reply"]
