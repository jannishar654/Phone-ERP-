from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.business_config import BusinessType


client = TestClient(app)


def table_query(data=None):
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.insert.return_value = query
    query.execute.return_value = MagicMock(data=data or [])
    return query


@patch("app.config.settings.settings.REQUIRE_AUTH", True)
def test_register_owner_uses_authenticated_user_and_selected_type():
    shops = table_query([])
    members = table_query([])
    shops.insert.return_value = table_query([{"id": "shop-1"}])

    with patch("app.dependencies.auth.supabase_client") as auth_client, patch(
        "app.routes.auth.supabase_client"
    ) as database, patch(
        "app.routes.auth.business_config_service.create_default_config"
    ) as create_config:
        auth_client.auth.get_user.return_value = MagicMock(
            user=MagicMock(id="owner-1")
        )
        database.table.side_effect = lambda name: {
            "shops": shops,
            "shop_members": members,
        }[name]

        response = client.post(
            "/auth/register-owner",
            json={"business_type": "restaurant", "shop_name": "Test Kitchen"},
            headers={"Authorization": "Bearer session-token"},
        )

    assert response.status_code == 200
    assert response.json()["shop_id"] == "shop-1"
    shops.insert.assert_called_once_with(
        {"owner_id": "owner-1", "name": "Test Kitchen", "phone": None}
    )
    create_config.assert_called_once_with("shop-1", BusinessType.restaurant)


@patch("app.config.settings.settings.REQUIRE_AUTH", True)
def test_register_owner_reuses_existing_shop_before_membership_check():
    shops = table_query([{"id": "existing-shop"}])

    with patch("app.dependencies.auth.supabase_client") as auth_client, patch(
        "app.routes.auth.supabase_client"
    ) as database, patch(
        "app.routes.auth.business_config_service.create_default_config"
    ) as create_config:
        auth_client.auth.get_user.return_value = MagicMock(
            user=MagicMock(id="owner-1")
        )
        database.table.return_value = shops
        response = client.post(
            "/auth/register-owner",
            json={"business_type": "wholesale"},
            headers={"Authorization": "Bearer session-token"},
        )

    assert response.status_code == 200
    assert response.json()["shop_id"] == "existing-shop"
    create_config.assert_called_once_with("existing-shop", BusinessType.wholesale)


@patch("app.config.settings.settings.REQUIRE_AUTH", True)
def test_register_owner_rejects_staff_account():
    shops = table_query([])
    members = table_query([{"id": "member-1", "role": "packer"}])

    with patch("app.dependencies.auth.supabase_client") as auth_client, patch(
        "app.routes.auth.supabase_client"
    ) as database:
        auth_client.auth.get_user.return_value = MagicMock(
            user=MagicMock(id="staff-1")
        )
        database.table.side_effect = lambda name: {
            "shops": shops,
            "shop_members": members,
        }[name]
        response = client.post(
            "/auth/register-owner",
            json={"business_type": "grocery"},
            headers={"Authorization": "Bearer session-token"},
        )

    assert response.status_code == 403


@patch("app.config.settings.settings.REQUIRE_AUTH", True)
def test_register_owner_rejects_unknown_business_type():
    with patch("app.dependencies.auth.supabase_client") as auth_client:
        auth_client.auth.get_user.return_value = MagicMock(
            user=MagicMock(id="owner-1")
        )
        response = client.post(
            "/auth/register-owner",
            json={"business_type": "unknown"},
            headers={"Authorization": "Bearer session-token"},
        )
    assert response.status_code == 422
