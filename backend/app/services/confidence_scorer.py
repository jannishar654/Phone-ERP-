from typing import Dict, Any, Tuple, List

class ConfidenceScorer:
    @staticmethod
    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @staticmethod
    def calculate_confidence(card_data: Any) -> Tuple[int, str, List[str]]:
        score = 100
        reasons = []

        # 1. Customer Missing
        customer_name = str(ConfidenceScorer._get(card_data, "customer_name") or "").strip().lower()
        if not customer_name or customer_name == "unknown":
            score -= 20
            reasons.append("Customer name is missing or unknown.")

        # 2. Address Missing
        delivery_address = str(ConfidenceScorer._get(card_data, "delivery_address") or "").strip().lower()
        if not delivery_address or delivery_address == "unknown":
            score -= 20
            reasons.append("Delivery address is missing.")

        # 3. Items Checks
        items = ConfidenceScorer._get(card_data, "items", [])
        if not items:
            score -= 40
            reasons.append("No items found in the order.")
        else:
            for item in items:
                name = ConfidenceScorer._get(item, "name", "Unknown Item")
                
                # Missing quantity or unit
                if ConfidenceScorer._get(item, "quantity") is None:
                    score -= 20
                    reasons.append(f"Missing quantity for: {name}")
                if not ConfidenceScorer._get(item, "unit"):
                    score -= 15
                    reasons.append(f"Missing unit for: {name}")
                
                # Missing price / unmatched catalog
                price = ConfidenceScorer._get(item, "price")
                try:
                    price_value = float(price or 0)
                except (TypeError, ValueError):
                    price_value = 0

                if price_value <= 0:
                    score -= 12
                    reasons.append(f"Price missing for {name}")

        # 4. Warnings and Risks
        validation_warnings = ConfidenceScorer._get(card_data, "validation_warnings", [])
        for warning in validation_warnings:
            w_lower = warning.lower()
            if "product_variant_unclear" in w_lower:
                score -= 10
                reasons.append("Product variant needs review.")
            elif "am/pm ambiguity" in w_lower:
                score -= 12
                reasons.append("AM/PM ambiguity in delivery time.")
            elif "large_quantity" in w_lower:
                score -= 2
                reasons.append("Large quantity detected, verify before approval.")
            elif "cancellation" in w_lower or "return" in w_lower or "previous order" in w_lower:
                score -= 8
                reasons.append(f"Operation risk: {warning}")

        # Unmapped cancellations/returns from metadata
        metadata = ConfidenceScorer._get(card_data, "metadata", {})
        cancelled_items = ConfidenceScorer._get(metadata, "cancelled_items", [])
        return_items = ConfidenceScorer._get(metadata, "return_items", [])
        previous_ref = ConfidenceScorer._get(metadata, "previous_order_reference")
        
        for item in cancelled_items:
            score -= 8
            reasons.append(f"Cancelled item handled: {item}")
        for item in return_items:
            score -= 8
            reasons.append(f"Return item handled: {item}")
        if previous_ref:
            score -= 8
            reasons.append("Previous order reference detected.")

        # 5. Delivery time missing
        delivery_time = str(ConfidenceScorer._get(card_data, "delivery_time", "")).strip()
        if not delivery_time or delivery_time.lower() == "unknown":
            score -= 8
            reasons.append("Delivery time is missing.")

        # 6. Raw LLM Confidence
        raw_confidence = float(ConfidenceScorer._get(card_data, "confidence", 1.0))
        if raw_confidence < 0.8:
            penalty = int((0.8 - raw_confidence) * 35)
            score -= penalty
            reasons.append(f"Low AI extraction confidence penalty (-{penalty}).")

        # Clamp
        score = max(0, min(100, int(score)))

        # Label
        if score >= 90:
            label = "High"
        elif score >= 70:
            label = "Medium"
        else:
            label = "Low"

        return score, label, reasons
