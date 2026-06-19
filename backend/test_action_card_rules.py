import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add backend dir to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from app.services.time_parser import parse_delivery_time
from app.services.quantity_parser import parse_quantity
from app.services.unit_normalizer import normalize_unit
from app.services.risk_detector import detect_risks
from app.services.business_memory import BusinessMemoryResolver

def run_tests():
    passed = 0
    total = 0
    
    print("--- Testing Deterministic Parsers ---\n")
    
    # 1. TIME PARSING
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    today_date = datetime.now().strftime('%Y-%m-%d')
    time_tests = [
        ("kal sade 8", f"{tomorrow_date} 8:30"),
        ("sawa chhe", f"{today_date} 6:15"),
        ("paune 5", f"{today_date} 4:45"),
        ("dhai baje", f"{today_date} 2:30 baje"),
        ("kal 10:15 pe", f"{tomorrow_date} 10:15 pe"),
        ("kal 5:30 baje", f"{tomorrow_date} 5:30 baje"),
        ("kal aisa karna 8:30 baje", f"{tomorrow_date} 8:30 baje"),
    ]
    print("1. Time Parsing:")
    for raw, expected_time in time_tests:
        res = parse_delivery_time(raw)
        if expected_time in str(res["normalized"]):
            print(f"  [PASS] '{raw}' -> {res['normalized']}")
            passed += 1
        else:
            print(f"  [FAIL] '{raw}' -> {res['normalized']} (Expected {expected_time})")
        total += 1
            
    # 2. QUANTITY PARSING
    quantity_tests = [
        ("aadha kilo", 0.5, "kilo"),
        ("dhai kilo", 2.5, "kilo"),
        ("sawa kilo", 1.25, "kilo"),
        ("paanch packet", 5.0, "packet"),
        ("sawa 2 litre", 2.25, "litre"),
        ("saade paanch kilo", 5.5, "kilo"),
        ("dhai litre", 2.5, "litre"),
        ("sare saath kilo", 7.5, "kilo"),
        ("do kilo", 2.0, "kilo"),
        ("missing", None, None)
    ]
    print("\n2. Quantity Parsing:")
    for raw, expected_qty, expected_unit in quantity_tests:
        total += 1
        res = parse_quantity(raw)
        if res["quantity"] == expected_qty and res["unit"] == expected_unit:
            print(f"  [PASS] '{raw}' -> {res['quantity']} {res['unit']}")
            passed += 1
        else:
            print(f"  [FAIL] '{raw}' -> Expected {expected_qty} {expected_unit}, got {res['quantity']} {res['unit']}")
            
    # 3. UNIT NORMALIZATION
    unit_tests = [
        ("peti", "carton"),
        ("carton", "carton"),
        ("packet", "packet"),
        ("kilo", "kg"),
        ("kilogram", "kg"),
        ("litre", "litre"),
        ("darjan", "dozen")
    ]
    print("\n3. Unit Normalization:")
    for raw, expected in unit_tests:
        total += 1
        res = normalize_unit(raw)
        if res == expected:
            print(f"  [PASS] '{raw}' -> {res}")
            passed += 1
        else:
            print(f"  [FAIL] '{raw}' -> Expected {expected}, got {res}")
            
    # 4. ALIAS RESOLUTION
    resolver = BusinessMemoryResolver()
    alias_tests = [
        ("lal surf", "Surf Excel Easy Wash"),
        ("chhota surf", "Surf Excel Rs 10 Pack"),
        ("bada doodh", "Amul Gold Milk 1L"),
        ("dus wala parle", "Parle-G Rs 10 Pack"),
        ("aata", "Aashirvaad Atta")
    ]
    print("\n4. Product Aliases:")
    for raw, expected in alias_tests:
        total += 1
        res = resolver.resolve_product(raw)
        if res == expected:
            print(f"  [PASS] '{raw}' -> {res}")
            passed += 1
        else:
            print(f"  [FAIL] '{raw}' -> Expected {expected}, got {res}")
            
    customer_tests = [
        ("jaaneeshaar", "Jannishar"),
        ("sharma ji", "Sharma Store"),
        ("gupta store", "Gupta Store")
    ]
    print("\n5. Customer Aliases:")
    for raw, expected in customer_tests:
        total += 1
        res = resolver.resolve_customer(raw)
        if res == expected:
            print(f"  [PASS] '{raw}' -> {res}")
            passed += 1
        else:
            print(f"  [FAIL] '{raw}' -> Expected {expected}, got {res}")

    # 6. RISK DETECTION
    risk_tests = [
        ("kal udhaar mein likh dena", [], ["credit_request"]),
        ("paisa udhaar rahega aur unka naam Shayam hai", [], ["credit_request"]),
        ("chips cancel kar do", [], ["cancellation"]),
        ("nahi hai toh substitute kar dena", [], ["substitution"]),
        ("scheme laga dena", [], ["discount"]),
        ("bhai jaldi bhejna", [], ["urgent"]),
        ("suno kal aisa karna gupta store shahin bag mein 15 kilo aalu 15 kilo tamatar 10.5 kilo pyaj 2.5 kilo chawal 0.5 kilo rasgulla aur chips ka packet 15 namak ka packet aur 15 badi doodh ki thaili aur 15 surf excel ka packet bhej dena unka naam Ram hai aur yeh udhar rahega aur haan kal wala chips cancel kar dena", [], ["credit_request", "cancellation"]),
        ("aaj", [{"name": "A", "quantity": 100, "unit": "packet", "price": 0}], ["large_quantity"]),
        ("50 kilo aalu bhej dena", [{"name": "aalu", "quantity": 50, "unit": "kg", "price": 0}], ["large_quantity"]),
        ("aaj", [{"name": "A", "quantity": 10, "unit": "packet", "price": 1000}], ["high_value"])
    ]
    print("\n6. Risk Detection:")
    for raw_transcript, items, expected_flags in risk_tests:
        total += 1
        res = detect_risks(raw_transcript, items)
        flags = res["risk_flags"]
        if all(flag in flags for flag in expected_flags):
            print(f"  [PASS] '{raw_transcript}' with {items} -> {flags}")
            passed += 1
        else:
            print(f"  [FAIL] '{raw_transcript}' -> Expected flags {expected_flags}, got {flags}")

    print(f"\nTotal: {total}, Passed: {passed}, Failed: {total - passed}")

    # 7. ACTION CARD VALIDATION
    print("\n7. Action Card Validation (qty > 0):")
    from app.services.action_card_validator import validate_action_card
    
    val_tests = [
        # Should pass
        ({"items": [{"name": "A", "quantity": 0.5}]}, []),
        # Should fail (negative/missing)
        ({"items": [{"name": "A", "quantity": -1}]}, ["quantity"]),
        ({"items": [{"name": "A", "quantity": None}]}, ["quantity"]),
    ]
    
    for card_data, expected_missing in val_tests:
        total += 1
        res = validate_action_card(card_data, "test")
        missing = res.get("missing_fields", [])
        if "quantity" in expected_missing and "quantity" in missing:
            print(f"  [PASS] Handled invalid quantity correctly.")
            passed += 1
        elif "quantity" not in expected_missing and "quantity" not in missing:
            print(f"  [PASS] Handled valid quantity correctly: {card_data}")
            passed += 1
        else:
            print(f"  [FAIL] Expected missing {expected_missing}, got {missing} for {card_data}")
            
    # 8. NAME CLEANUP PARSING
    print("\n8. Name Cleanup Parsing:")
    import re
    def mock_extract_name(transcript):
        cust_name = "Unknown"
        t_lower = transcript.lower()
        if not cust_name or cust_name.lower() == "unknown":
            name_match = re.search(r'(?:unka naam|naam|customer ka naam|party ka naam)\s+(.*?)(?:\s+hai|\s+tha|\s+aur|$)', t_lower)
            if name_match:
                cust_name = name_match.group(1).strip().title()
        if cust_name and cust_name != "Unknown":
            cust_name = re.sub(r'(?:\s+(?:likhna|likh\s*dena|likhdo|rakhna|karna|bhejna|dena|hai|theek\s*hai))+$', '', cust_name, flags=re.IGNORECASE).strip()
        return cust_name

    name_cleanup_tests = [
        ("unka naam Danish Likhna", "Danish"),
        ("naam danish likhna", "Danish"),
        ("party ka naam Ram hai theek hai", "Ram")
    ]
    for transcript, expected in name_cleanup_tests:
        cleaned = mock_extract_name(transcript)
        if cleaned == expected:
            print(f"  [PASS] '{transcript}' -> '{cleaned}'")
            passed += 1
        else:
            print(f"  [FAIL] '{transcript}' -> '{cleaned}' (Expected '{expected}')")
        total += 1
            
    # 9. DETERMINISTIC AGGREGATION
    print("\n9. Deterministic Aggregation:")
    from app.services.gemini import aggregate_items_deterministically
    
    agg_tests = [
        # 50 kg atta + 15 kg atta = 65 kg
        (
            [{"name": "atta", "quantity": 50, "unit": "kg"}, {"name": "atta", "quantity": 15, "unit": "kg"}],
            [{"name": "atta", "quantity": 65, "unit": "kg"}]
        ),
        # 2.5 kg atta + 0.5 kg atta = 3 kg (should be converted to int if flat)
        (
            [{"name": "atta", "quantity": 2.5, "unit": "kg"}, {"name": "atta", "quantity": 0.5, "unit": "kg"}],
            [{"name": "atta", "quantity": 3, "unit": "kg"}]
        ),
        # atta and chawal remain separate
        (
            [{"name": "atta", "quantity": 10, "unit": "kg"}, {"name": "chawal", "quantity": 20, "unit": "kg"}],
            [{"name": "atta", "quantity": 10, "unit": "kg"}, {"name": "chawal", "quantity": 20, "unit": "kg"}]
        ),
        # 1 packet Surf variant A and 1 packet Surf variant B remain separate
        (
            [{"name": "Surf Excel Rs 10", "quantity": 1, "unit": "packet"}, {"name": "Surf Excel Matic", "quantity": 1, "unit": "packet"}],
            [{"name": "Surf Excel Rs 10", "quantity": 1, "unit": "packet"}, {"name": "Surf Excel Matic", "quantity": 1, "unit": "packet"}]
        ),
        # missing quantity does not crash or become zero
        (
            [{"name": "atta", "quantity": None, "unit": "kg"}, {"name": "atta", "quantity": 10, "unit": "kg"}],
            [{"name": "atta", "quantity": 10, "unit": "kg"}]
        ),
        # already aggregated 65 kg item remains 65 kg (when run again or returned alone)
        (
            [{"name": "atta", "quantity": 65, "unit": "kg"}],
            [{"name": "atta", "quantity": 65, "unit": "kg"}]
        )
    ]
    
    for raw_items, expected_agg in agg_tests:
        agg = aggregate_items_deterministically(raw_items)
        
        # compare ignoring order
        def norm(lst):
            return sorted([{k: v for k, v in i.items() if k in ["name", "quantity", "unit"]} for i in lst], key=lambda x: str(x))
            
        if norm(agg) == norm(expected_agg):
            print(f"  [PASS] Aggregation logic: {raw_items} -> {agg}")
            passed += 1
        else:
            print(f"  [FAIL] Expected {expected_agg}, got {agg}")
        total += 1

    # final large_quantity risk is detected on aggregated items
    agg_items = aggregate_items_deterministically([{"name": "atta", "quantity": 30, "unit": "kg"}, {"name": "atta", "quantity": 20, "unit": "kg"}])
    risks = detect_risks("transcript", agg_items).get("risk_flags", [])
    if "large_quantity" in risks:
        print(f"  [PASS] large_quantity detected correctly on aggregated 50kg atta.")
        passed += 1
    else:
        print(f"  [FAIL] large_quantity not detected on aggregated 50kg atta. Risks: {risks}")
    total += 1

    print(f"\nFinal -> Total: {total}, Passed: {passed}, Failed: {total - passed}")

if __name__ == "__main__":
    run_tests()
