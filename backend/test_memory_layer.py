import sys
import os

# Add backend directory to sys.path to allow importing app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.business_memory import business_memory

def run_tests():
    print("--- Testing Business Memory Layer ---")

    # Reload to ensure we have the latest data
    business_memory.reload()

    test_cases = [
        # --- Local Alias Exact Matches ---
        {"raw": "bada doodh", "customer_id": "unknown", "expected": "Amul Gold Milk 1L", "desc": "Local exact match"},
        {"raw": "lal surf", "customer_id": "unknown", "expected": "Surf Excel Easy Wash", "desc": "Local exact match"},
        {"raw": "dus wala parle", "customer_id": "unknown", "expected": "Parle-G Rs 10 Pack", "desc": "Local exact match"},
        {"raw": "aata", "customer_id": "unknown", "expected": "Aashirvaad Atta", "desc": "Local exact match"},

        # --- Fuzzy/Case-insensitive Matches ---
        {"raw": "  LAL SURF  ", "customer_id": "unknown", "expected": "Surf Excel Easy Wash", "desc": "Case-insensitive match"},
        {"raw": "laal surf", "customer_id": "unknown", "expected": "Surf Excel Easy Wash", "desc": "Fuzzy match for 'laal surf' -> 'lal surf'"},
        {"raw": "chawal", "customer_id": "unknown", "expected": "India Gate Basmati Rice", "desc": "Local exact match"},

        # --- Customer Specific Matches (Override local) ---
        {"raw": "chotu surf", "customer_id": "Jannishar", "expected": "Surf Excel Rs 10 Pack", "desc": "Customer specific unique alias"},
        {"raw": "mera regular", "customer_id": "Danish", "expected": "Parle-G Rs 10 Pack", "desc": "Customer specific unique alias"},

        # --- Customer Fallback to Local ---
        {"raw": "lal surf", "customer_id": "Nasir", "expected": "Surf Excel Easy Wash", "desc": "Customer fallback to local"},
        {"raw": "nila packet", "customer_id": "Nasir", "expected": "Lays India's Magic Masala", "desc": "Customer specific override"},
        {"raw": "nila packet", "customer_id": "unknown", "expected": "nila packet", "desc": "No match fallback"},

        # --- No Match (Should return original string) ---
        {"raw": "unknown random product", "customer_id": "unknown", "expected": "unknown random product", "desc": "No match fallback"},
        {"raw": "kellogs chocos", "customer_id": "Danish", "expected": "kellogs chocos", "desc": "No match fallback"}
    ]

    passed = 0
    failed = 0

    for idx, case in enumerate(test_cases, 1):
        raw = case["raw"]
        cid = case["customer_id"]
        expected = case["expected"]

        result = business_memory.resolve_product(raw, customer_id=cid)

        if result == expected:
            print(f"✅ Test {idx} PASSED ({case['desc']})")
            passed += 1
        else:
            print(f"❌ Test {idx} FAILED ({case['desc']})")
            print(f"   Input    : '{raw}' (Customer: {cid})")
            print(f"   Expected : '{expected}'")
            print(f"   Got      : '{result}'")
            failed += 1

    print("-" * 35)
    print(f"Total: {len(test_cases)} | Passed: {passed} | Failed: {failed}")

    print("\n--- Testing Business Alias Modes ---")
    from app.config.settings import settings

    # Mode OFF
    settings.BUSINESS_ALIAS_MODE = "off"
    res_off = business_memory.resolve_product_detailed("lal surf")
    if res_off["name"] == "lal surf" and res_off["canonical_name"] is None:
        print("✅ Mode OFF: Passed")
    else:
        print(f"❌ Mode OFF: Failed - {res_off}")
        failed += 1

    # Mode SUGGEST
    settings.BUSINESS_ALIAS_MODE = "suggest"
    res_suggest = business_memory.resolve_product_detailed("lal surf")
    if res_suggest["name"] == "lal surf" and res_suggest["canonical_name"] == "Surf Excel Easy Wash" and res_suggest["resolution_status"] == "suggested":
        print("✅ Mode SUGGEST: Passed")
    else:
        print(f"❌ Mode SUGGEST: Failed - {res_suggest}")
        failed += 1

    # Mode APPLY
    settings.BUSINESS_ALIAS_MODE = "apply"
    res_apply = business_memory.resolve_product_detailed("lal surf")
    if res_apply["name"] == "Surf Excel Easy Wash" and res_apply["alias_used"] is True and res_apply["resolution_status"] == "applied":
        print("✅ Mode APPLY: Passed")
    else:
        print(f"❌ Mode APPLY: Failed - {res_apply}")
        failed += 1

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Business Memory Layer is ready.")
    else:
        print(f"\n⚠️ SOME TESTS FAILED. ({failed} total failures)")

if __name__ == "__main__":
    run_tests()
