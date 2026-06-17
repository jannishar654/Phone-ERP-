import sys
import os

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
    time_tests = [
        ("kal sade 8", "8:30"),
        ("sawa chhe", "6:15"),
        ("paune 5", "4:45"),
        ("dhai baje", "2:30"),
        ("kal 10:15 pe", "10:15")
    ]
    print("1. Time Parsing:")
    for raw, expected_time in time_tests:
        total += 1
        res = parse_delivery_time(raw)
        norm = res["normalized"] or ""
        if expected_time in norm:
            print(f"  [PASS] '{raw}' -> {norm}")
            passed += 1
        else:
            print(f"  [FAIL] '{raw}' -> Expected to contain {expected_time}, got {norm}")
            
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
        ("chips cancel kar do", [], ["cancellation"]),
        ("nahi hai toh substitute kar dena", [], ["substitution"]),
        ("scheme laga dena", [], ["discount"]),
        ("bhai jaldi bhejna", [], ["urgent"]),
        ("aaj", [{"name": "A", "quantity": 100, "unit": "packet", "price": 0}], ["large_quantity"]),
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
    
if __name__ == "__main__":
    run_tests()
