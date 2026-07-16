from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_customer_portal_preflight_allows_production_frontend():
    response = client.options(
        "/customer/access/exchange",
        headers={
            "Origin": "https://phone-erp.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://phone-erp.vercel.app"
    )
    assert "POST" in response.headers["access-control-allow-methods"]


def test_customer_portal_preflight_rejects_untrusted_origin():
    response = client.options(
        "/customer/access/exchange",
        headers={
            "Origin": "https://malicious.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
