import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.operation_reducer import OperationReducer
from app.schemas.order_operation import OrderOperation

def run_tests():
    print("--- Testing Operation Reducer ---")

    test_cases = [
        {
            "name": "1. Add then Set Quantity",
            "operations": [
                {"sequence": 1, "operation_id": "op1", "type": "ADD", "raw_product": "sugar", "quantity": 5, "unit": "kilo", "evidence": "sugar 5 kilo"},
                {"sequence": 2, "target_operation_id": "op1", "type": "SET_QUANTITY", "raw_product": "sugar", "quantity": 2, "unit": "kilo", "evidence": "nahi 2 kilo hi bhej dena"}
            ],
            "expected_items": [{"operation_id": "op1", "name": "sugar", "raw_name": "sugar", "quantity": 2.0, "unit": "kilo"}],
            "expected_cancelled": []
        },
        {
            "name": "Unit correction only (15 kilo oil nahi 15 litre oil)",
            "operations": [
                {"sequence": 1, "operation_id": "op2", "type": "ADD", "raw_product": "oil", "quantity": 15, "unit": "kilo", "evidence": "15 kilo oil"},
                {"sequence": 2, "target_operation_id": "op2", "type": "SET_QUANTITY", "raw_product": "oil", "unit": "litre", "evidence": "nahi 15 litre oil"}
            ],
            "expected_items": [{"operation_id": "op2", "name": "oil", "raw_name": "oil", "quantity": 15.0, "unit": "litre"}],
            "expected_cancelled": []
        },
        {
            "name": "Quantity correction only (5 kilo chawal nahi 10 kilo chawal)",
            "operations": [
                {"sequence": 1, "operation_id": "op3", "type": "ADD", "raw_product": "chawal", "quantity": 5, "unit": "kilo", "evidence": "5 kilo chawal"},
                {"sequence": 2, "target_operation_id": "op3", "type": "SET_QUANTITY", "raw_product": "chawal", "quantity": 10, "evidence": "nahi 10 kilo chawal"}
            ],
            "expected_items": [{"operation_id": "op3", "name": "chawal", "raw_name": "chawal", "quantity": 10.0, "unit": "kg"}],
            "expected_cancelled": []
        },
        {
            "name": "Unit correction with different name (2 packet surf nahi 2 carton surf)",
            "operations": [
                {"sequence": 1, "type": "ADD", "raw_product": "surf", "quantity": 2, "unit": "packet", "evidence": "2 packet surf"},
                {"sequence": 2, "type": "SET_QUANTITY", "raw_product": "surf", "unit": "carton", "evidence": "nahi 2 carton surf"}
            ],
            "expected_items": [{"operation_id": None, "name": "surf", "raw_name": "surf", "quantity": 2.0, "unit": "carton"}],
            "expected_cancelled": []
        },
        {
            "name": "2. Return plus new order",
            "operations": [
                {"sequence": 1, "type": "RETURN", "raw_product": "biscuits", "quantity": 2, "unit": "packet", "evidence": "2 packet biscuits wapas le lo"},
                {"sequence": 2, "type": "ADD", "raw_product": "chini", "quantity": 0.5, "unit": "kilo", "evidence": "aadha kilo chini bhej dena"}
            ],
            "expected_items": [{"operation_id": None, "name": "chini", "raw_name": "chini", "quantity": 0.5, "unit": "kilo"}],
            "expected_return": [{"name": "biscuits", "quantity": 2.0, "unit": "packet", "evidence": "2 packet biscuits wapas le lo"}]
        },
        {
            "name": "3. Previous order reference",
            "operations": [
                {"sequence": 1, "type": "PREVIOUS_ORDER_REFERENCE", "raw_product": "pichli baar wala order", "evidence": "pichli baar wala order bhej dena"}
            ],
            "expected_items": [],
            "expected_prev": "pichli baar wala order bhej dena"
        },
        {
            "name": "4. Substitution",
            "operations": [
                {"sequence": 1, "type": "SUBSTITUTE", "raw_product": "Surf", "condition": "Surf na mile toh sasta wala de dena", "evidence": "Surf na mile toh sasta wala de dena"}
            ],
            "expected_items": [],
            "expected_sub": [{"name": "Surf", "condition": "Surf na mile toh sasta wala de dena", "evidence": "Surf na mile toh sasta wala de dena"}]
        },
        {
            "name": "5. Add then cancel",
            "operations": [
                {"sequence": 1, "operation_id": "op1", "type": "ADD", "raw_product": "Tide", "quantity": 1, "evidence": "ek Tide bhej dena"},
                {"sequence": 2, "target_operation_id": "op1", "type": "CANCEL", "raw_product": "Tide", "evidence": "Tide cancel kar dena"}
            ],
            "expected_items": [],
            "expected_cancelled": [{"operation_id": "op1", "name": "Tide", "raw_name": "Tide", "quantity": 1.0, "unit": None}]
        },
        {
            "name": "6. Ambiguity Test (duplicate ADD then CANCEL)",
            "operations": [
                {"sequence": 1, "type": "ADD", "raw_product": "Surf", "quantity": 1, "evidence": "surf"},
                {"sequence": 2, "type": "ADD", "raw_product": "Surf", "quantity": 2, "evidence": "aur surf"},
                {"sequence": 3, "type": "CANCEL", "raw_product": "Surf", "evidence": "surf hata do"}
            ],
            "expected_items": [
                {"operation_id": None, "name": "Surf", "raw_name": "Surf", "quantity": 1.0, "unit": None},
                {"operation_id": None, "name": "Surf", "raw_name": "Surf", "quantity": 2.0, "unit": None}
            ],
            "expected_warnings": ["Ambiguity Warning: Multiple matches for CANCEL 'Surf'. Operation preserved in warnings."]
        },
        {
            "name": "7. Invalid operation type",
            "operations": [
                {"sequence": 1, "type": "INVALID_TYPE", "raw_product": "Surf", "evidence": "bad"}
            ],
            "expected_items": [],
            "expected_invalid": True
        },
        {
            "name": "8. Missing/Duplicate sequence values",
            "operations": [
                {"sequence": None, "type": "SET_QUANTITY", "raw_product": "Surf", "quantity": 5, "evidence": "missing seq", "target_operation_id": "op1"},
                {"sequence": 1, "operation_id": "op1", "type": "ADD", "raw_product": "Surf", "quantity": 1, "evidence": "add"},
                {"sequence": 1, "type": "ADD", "raw_product": "Duplicate", "quantity": 1, "evidence": "duplicate"}
            ],
            "expected_items": [{"operation_id": "op1", "name": "Surf", "raw_name": "Surf", "quantity": 1.0, "unit": None}],
            "expected_invalid": True,
            "expected_warnings": ["Review Required: Unparseable or invalid operations detected."]
        },
        {
            "name": "9. SET_QUANTITY target missing",
            "operations": [
                {"sequence": 1, "type": "SET_QUANTITY", "raw_product": "Unknown", "quantity": 1, "evidence": "unknown"}
            ],
            "expected_items": [],
            "expected_warnings": ["Quantity update requested for 'Unknown' but item not found in order."]
        },
        {
            "name": "10. Fractional quantity recovery",
            "operations": [
                {"sequence": 1, "type": "ADD", "raw_product": "aadha kilo cheeni", "evidence": "aadha kilo cheeni"},
                {"sequence": 2, "type": "ADD", "raw_product": "sawa kilo doodh", "evidence": "sawa kilo doodh bhej dena"},
                {"sequence": 3, "type": "ADD", "raw_product": "chawal", "evidence": "2.5 kilo chawal"},
                {"sequence": 4, "type": "ADD", "raw_product": "chips", "evidence": "chips ka packet missing qty"}
            ],
            "expected_items": [
                {"operation_id": None, "name": "cheeni", "raw_name": "cheeni", "quantity": 0.5, "unit": "kg"},
                {"operation_id": None, "name": "doodh", "raw_name": "doodh", "quantity": 1.25, "unit": "kg"},
                {"operation_id": None, "name": "chawal", "raw_name": "chawal", "quantity": 2.5, "unit": "kg"},
                {"operation_id": None, "name": "chips", "raw_name": "chips", "quantity": None, "unit": "packet"}
            ]
        },
        {
            "name": "11. Evidence parsing safety (avoid arbitrary numbers)",
            "operations": [
                {"sequence": 1, "type": "ADD", "raw_product": "Surf Excel", "evidence": "Surf Excel 10 wala bhej do"},
                {"sequence": 2, "type": "ADD", "raw_product": "Parle-G Rs 10 pack", "evidence": "Parle-G Rs 10 pack dena"}
            ],
            "expected_items": [
                {"operation_id": None, "name": "Surf Excel", "raw_name": "Surf Excel", "quantity": None, "unit": None},
                {"operation_id": None, "name": "Parle-G Rs 10 pack", "raw_name": "Parle-G Rs 10 pack", "quantity": None, "unit": None}
            ]
        },
        {
            "name": "12. Add more of same item (aur jod dena)",
            "operations": [
                {"sequence": 1, "type": "ADD", "raw_product": "aata", "quantity": 5, "unit": "kilo", "evidence": "5 kilo aata bhej dena"},
                {"sequence": 2, "type": "ADD", "raw_product": "aata", "quantity": 15, "unit": "kilo", "evidence": "aata mein bhi 15 kilo aata aur jod dena"}
            ],
            "expected_items": [
                {"operation_id": None, "name": "aata", "raw_name": "aata", "quantity": 5.0, "unit": "kilo"},
                {"operation_id": None, "name": "aata", "raw_name": "aata", "quantity": 15.0, "unit": "kilo"}
            ]
        }
    ]

    failed = 0
    passed = 0

    for idx, case in enumerate(test_cases, 1):
        res = OperationReducer.parse_and_reduce(case["operations"])

        errs = []

        # Check active items
        if res["active_items"] != case.get("expected_items", []):
            errs.append(f"Active items mismatch. Expected {case.get('expected_items', [])}, got {res['active_items']}")

        # Check cancelled
        if "expected_cancelled" in case and res["cancelled_items"] != case["expected_cancelled"]:
            errs.append(f"Cancelled items mismatch. Expected {case['expected_cancelled']}, got {res['cancelled_items']}")

        # Check return
        if "expected_return" in case and res["return_items"] != case["expected_return"]:
            errs.append(f"Return items mismatch. Expected {case['expected_return']}, got {res['return_items']}")

        # Check substitute
        if "expected_sub" in case and res["substitution_instructions"] != case["expected_sub"]:
            errs.append(f"Substitution items mismatch. Expected {case['expected_sub']}, got {res['substitution_instructions']}")

        # Check previous order
        if "expected_prev" in case and res["previous_order_reference"] != case["expected_prev"]:
            errs.append(f"Previous order mismatch. Expected {case['expected_prev']}, got {res['previous_order_reference']}")

        # Check warnings
        if "expected_warnings" in case:
            for w in case["expected_warnings"]:
                if w not in res["operation_warnings"]:
                    errs.append(f"Missing expected warning: '{w}'. Got: {res['operation_warnings']}")

        # Check invalid
        if case.get("expected_invalid") and not res["invalid_operations"]:
            errs.append("Expected invalid operations but found none.")

        if errs:
            print(f"❌ Test {idx} FAILED ({case['name']})")
            for e in errs:
                print(f"   {e}")
            failed += 1
        else:
            print(f"✅ Test {idx} PASSED ({case['name']})")
            passed += 1

    total = len(test_cases)
    print("\n--- Testing Quantity Parser Direct Tests ---")
    from app.services.quantity_parser import parse_quantity

    pq_res1 = parse_quantity("Surf Excel 10 wala")
    if pq_res1["quantity"] is None and pq_res1["cleaned_text"] == "Surf Excel 10 wala":
        print(f"✅ [PASS] 'Surf Excel 10 wala' -> quantity=None, cleaned_text unchanged")
        passed += 1
    else:
        print(f"❌ [FAIL] 'Surf Excel 10 wala' failed, got: {pq_res1}")
    total += 1

    pq_res2 = parse_quantity("Parle-G Rs 10 pack")
    if pq_res2["quantity"] is None and pq_res2["cleaned_text"] == "Parle-G Rs 10 pack":
        print(f"✅ [PASS] 'Parle-G Rs 10 pack' -> quantity=None, cleaned_text unchanged")
        passed += 1
    else:
        print(f"❌ [FAIL] 'Parle-G Rs 10 pack' failed, got: {pq_res2}")
    total += 1

    pq_res3 = parse_quantity("aadha kilo cheeni")
    if pq_res3["quantity"] == 0.5 and pq_res3["unit"] == "kg" and pq_res3["cleaned_text"] == "cheeni":
        print(f"✅ [PASS] 'aadha kilo cheeni' -> 0.5 kg cheeni")
        passed += 1
    else:
        print(f"❌ [FAIL] 'aadha kilo cheeni' failed, got: {pq_res3}")
    total += 1

    print("-" * 35)
    print(f"Total: {total} | Passed: {passed} | Failed: {total - passed}")
    if passed != total:
        print("⚠️ SOME TESTS FAILED.")
        import sys
        sys.exit(1)
    else:
        print("🎉 ALL TESTS PASSED! Operation Reducer is ready.")

if __name__ == "__main__":
    run_tests()
