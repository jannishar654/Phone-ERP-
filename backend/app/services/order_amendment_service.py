from typing import Any, Dict, Iterable, List

from app.services.matching_service import matching_service


def normalize_amendment_items(
    shop_id: str,
    items: Iterable[Any],
) -> List[Dict[str, Any]]:
    """Resolve customer-entered products against the shop catalog.

    Customer payloads never control prices or catalog identifiers. Unmatched items
    remain visible for the owner with a pending-price marker.
    """
    normalized: List[Dict[str, Any]] = []
    for item in items:
        payload = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        raw_name = str(payload.get("name") or "").strip()
        if not raw_name:
            continue
        quantity = float(payload["quantity"])
        match = matching_service.match_product(raw_name, shop_id)
        matched = match.get("resolution_status") in {"matched", "suggested"}
        unit_price = float(match.get("unit_price") or 0) if matched else 0.0
        unit = str(payload.get("unit") or match.get("unit") or "").strip()
        display_name = match.get("display_name") or raw_name
        normalized.append(
            {
                "name": display_name,
                "raw_name": raw_name,
                "canonical_name": match.get("canonical_name"),
                "quantity": quantity,
                "unit": unit,
                "price": unit_price,
                "price_status": None if matched else "Pending Price Verification",
                "resolution_status": match.get("resolution_status") or "unmatched",
                "possible_matches": match.get("possible_matches") or [],
                "metadata": {
                    "catalog_item_id": match.get("catalog_item_id"),
                },
            }
        )
    if not normalized:
        raise ValueError("At least one valid item is required")
    return normalized
