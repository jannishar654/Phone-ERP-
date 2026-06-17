from typing import Dict, Any, List

def detect_risks(transcript: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    risk_flags = []
    validation_warnings = []
    
    t_lower = str(transcript).lower()
    
    # 1. Credit Request
    if any(word in t_lower for word in ["udhaar", "credit", "baad mein", "udhar", "उधार", "बाद में", "बाकी", "hisaab mein likh", "hisaab me likh"]):
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
        
    # Payment method extraction
    payment_method = "Not Specified"
    if "credit_request" in risk_flags:
        payment_method = "Credit (Udhaar)"
    elif any(word in t_lower for word in ["cash", "nagad", "nakad", "नकद", "कैश"]):
        payment_method = "Cash"
    elif any(word in t_lower for word in ["online", "upi", "paytm", "gpay", "phonepe", "ऑनलाइन", "यूपीआई", "पेटीएम"]):
        payment_method = "Online"

    return {
        "risk_flags": risk_flags,
        "validation_warnings": validation_warnings,
        "payment_method": payment_method
    }
