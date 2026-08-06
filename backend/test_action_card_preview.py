from unittest.mock import patch

from app.routes.endpoints import _preview_card_from_extracted


def test_action_card_preview_does_not_persist():
    extracted = {
        "customer_name": "Danish",
        "customer_phone": "9065440786",
        "items": [{"name": "Rice", "quantity": 5, "unit": "kg", "price": 60}],
        "delivery_address": "Batla House, Jamia Nagar",
        "delivery_time": "Tomorrow, 8 PM",
        "payment_method": "cash",
    }

    with patch("app.routes.endpoints.ActionCardController.create_card") as create_card:
        preview = _preview_card_from_extracted(extracted, "send five kg rice", None)

    create_card.assert_not_called()
    assert preview.customer_name == "Danish"
    assert preview.customer_phone == "+919065440786"
    assert preview.items[0].name == "Rice"
    assert preview.items[0].quantity == 5
    assert preview.status == "pending"
    assert preview.metadata["preview_only"] is True
