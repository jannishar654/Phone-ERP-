from typing import Dict, Any, List

import re

def detect_payment_method(transcript: str) -> str:
    """
    Deterministically detects explicit payment intent from a transcript using safe word boundaries.
    Returns: "Credit (Udhaar)", "Cash", "Online", or "Not Specified"
    """
    t_lower = str(transcript).lower()

    # 1. Credit Request
    credit_pattern = r'\b(udhaar|udhar|credit|baad mein|baaki|hisaab mein likh|hisaab me likh|paisa udhaar|khata|khate|उधार|बाद में|बाकी)\b'
    if re.search(credit_pattern, t_lower):
        return "Credit (Udhaar)"

    # 2. Cash Request
    cash_pattern = r'\b(cash|nagad|nakad|नकद|कैश)\b'
    if re.search(cash_pattern, t_lower):
        return "Cash"

    # 3. Online Request
    online_pattern = r'\b(online payment|online pay|upi|gpay|google\s*pay|phonepe|paytm|ऑनलाइन|यूपीआई|पेटीएम)\b'
    if re.search(online_pattern, t_lower):
        return "Online"

    return "Not Specified"

def detect_risks(transcript: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    risk_flags = []
    validation_warnings = []

    t_lower = str(transcript).lower()

    # 1. Credit Request
    payment_method = detect_payment_method(transcript)
    if payment_method == "Credit (Udhaar)":
        risk_flags.append("credit_request")
        validation_warnings.append("Customer requested credit/udhaar.")

    # 2. Cancellation
    if any(word in t_lower for word in ["cancel", "cancellation", "radd", "रद्द", "कैंसिल", "mat bhejna", "hata do"]):
        risk_flags.append("cancellation")
        validation_warnings.append("Order cancellation mentioned.")

    # 3. Substitution
    if any(word in t_lower for word in ["replace", "substitute", "badal", "nahi hai toh", "बदल", "नहीं है तो"]):
        risk_flags.append("substitution")
        validation_warnings.append("Product substitution or replacement mentioned.")

    # 4. Discount / Scheme
    if any(word in t_lower for word in ["scheme", "discount", "offer", "sasta", "स्कीम", "डिस्काउंट", "सस्ता"]):
        risk_flags.append("discount")
        validation_warnings.append("Customer asked for scheme/discount.")

    # 5. Urgent Request
    if any(word in t_lower for word in ["urgent", "aaj hi", "jaldi", "तुरंत", "जल्दी", "आज ही"]):
        risk_flags.append("urgent")
        validation_warnings.append("Customer requested urgent delivery.")

    # 6. Expensive / Large Quantity checks (MVP Thresholds)
    THRESHOLDS = {
        "packet": 50,
        "kg": 25,
        "carton": 10,
        "dozen": 20,
        "litre": 20,
        "fallback": 20
    }
    PRICE_THRESHOLD = 5000

    total_price = 0.0
    for item in items:
        qty = item.get("quantity")
        unit = str(item.get("unit", "")).lower()
        price = item.get("price")
        name = item.get("name", "Unknown Item")

        # Calculate total price if available
        if price is not None and isinstance(price, (int, float)) and qty is not None and isinstance(qty, (int, float)):
            total_price += price * qty

        # Check quantity thresholds
        if qty is not None and isinstance(qty, (int, float)):
            threshold = THRESHOLDS.get(unit, THRESHOLDS["fallback"])
            if qty > threshold:
                if "large_quantity" not in risk_flags:
                    risk_flags.append("large_quantity")
                validation_warnings.append(f"Unusually large quantity detected for {name} ({qty} {unit}).")

    if total_price > PRICE_THRESHOLD:
        risk_flags.append("high_value")
        validation_warnings.append(f"Order total value (₹{total_price}) exceeds risk threshold (₹{PRICE_THRESHOLD}).")

    return {
        "risk_flags": risk_flags,
        "validation_warnings": validation_warnings,
        "payment_method": payment_method
    }
