from typing import Dict, Any, List

def validate_action_card(extracted_data: Dict[str, Any], transcript: str) -> Dict[str, List[str]]:
    risk_flags = []
    missing_fields = []
    validation_warnings = []

    # Check missing fields
    cust_name = extracted_data.get("customer_name")
    if not cust_name or str(cust_name).lower() == "unknown":
        missing_fields.append("customer_name")
    
    if not extracted_data.get("delivery_address"):
        missing_fields.append("delivery_address")
        
    items = extracted_data.get("items", [])
    if not items:
        missing_fields.append("items")
    else:
        for item in items:
            qty = item.get("quantity")
            # Quantity must be a valid positive number (>0). If it's a string (e.g. gibberish fallback), None, or <=0, mark missing
            if qty is None or not isinstance(qty, (int, float)) or qty <= 0:
                missing_fields.append("quantity")
                
            unit = item.get("unit")
            if not unit or str(unit).strip().lower() in ("none", "null", ""):
                if item.get("price") == 0.0:  # Only flag missing unit if it's not a price-based item
                    missing_fields.append("unit")
                    validation_warnings.append(f"Missing unit for '{item.get('name')}'.")
                
            # If the product didn't match the catalog
            if not item.get("matched", True):
                missing_fields.append("product_variant_unclear")
                possible = item.get("possible_matches", [])
                msg = f"Ambiguous product '{item.get('name')}'. "
                if possible:
                    msg += f"Did you mean: {', '.join(possible)}?"
                else:
                    msg += "No catalog match found."
                validation_warnings.append(msg)
                
    # Risk detection is now handled centrally by risk_detector.py
    # We just need to merge any missing fields here
    
    return {
        "missing_fields": list(dict.fromkeys(missing_fields)),
        "warnings": validation_warnings
    }
