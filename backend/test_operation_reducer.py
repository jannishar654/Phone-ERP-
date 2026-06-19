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
                {"sequence": 1, "operation_id": "op1", "type": "ADD", "raw_product": "Surf", "quantity": 1, "evidence": "add"}
            ],
            "expected_items": [{"operation_id": "op1", "name": "Surf", "raw_name": "Surf", "quantity": 5.0, "unit": None}],
        },
        {
            "name": "9. SET_QUANTITY target missing",
            "operations": [
                {"sequence": 1, "type": "SET_QUANTITY", "raw_product": "Unknown", "quantity": 1, "evidence": "unknown"}
            ],
            "expected_items": [],
            "expected_warnings": ["Quantity update requested for 'Unknown' but item not found in order."]
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

    print("-" * 35)
    print(f"Total: {len(test_cases)} | Passed: {passed} | Failed: {failed}")
    if failed == 0:
        print("🎉 ALL TESTS PASSED! Operation Reducer is ready.")
    else:
        print("⚠️ SOME TESTS FAILED.")

if __name__ == "__main__":
    run_tests()
