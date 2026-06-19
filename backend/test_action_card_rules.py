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
        ("kal sade 8", f"{tomorrow_date} 8:30", None),
        ("sawa chhe", None, "Missing specific day"),
        ("paune 5", None, "Missing specific day"),
        ("dhai baje", None, "Missing specific day"),
        ("kal 10:15 pe", f"{tomorrow_date} 10:15 pe", None),
        ("kal 5:30 baje", f"{tomorrow_date} 5:30 baje", None),
        ("kal aisa karna 8:30 baje", f"{tomorrow_date} 8:30 baje", None),
        ("kalle esa karna 5:30 baje", f"{tomorrow_date} 5:30 baje", "Interpreted 'kalle' as 'kal'"),
        ("kal ka order cancel karo, aaj 5 baje naya bhejna", f"{today_date} 5 baje", None),
        ("5:30 baje bhejna", None, "Missing specific day"),
        ("kalle", None, "Uncertain delivery time"), # unrelated kalle without clock
    ]
    print("1. Time Parsing:")
    for raw, expected_time, expected_warning in time_tests:
        res = parse_delivery_time(raw)
        
        time_match = expected_time is None and res["normalized"] is None
        if not time_match and expected_time is not None and res["normalized"] is not None:
            time_match = expected_time in str(res["normalized"])
            
        warning_match = expected_warning is None or (res["warning"] and expected_warning in res["warning"])
        
        if time_match and warning_match:
            print(f"  [PASS] '{raw}' -> {res['normalized']} (Warning: {res['warning']})")
            passed += 1
        else:
            print(f"  [FAIL] '{raw}' -> {res['normalized']} | Expected: {expected_time}. Warning: {res['warning']} | Expected Warning: {expected_warning}")
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
        ({"customer_name": "Danish", "delivery_address": "Here", "items": [{"name": "A", "quantity": 0.5, "unit": "kg", "price": 0.0}]}, []),
        # Should fail (negative/missing quantity)
        ({"customer_name": "Danish", "delivery_address": "Here", "items": [{"name": "A", "quantity": -1, "unit": "kg"}]}, ["quantity"]),
        ({"customer_name": "Danish", "delivery_address": "Here", "items": [{"name": "A", "quantity": None, "unit": "kg"}]}, ["quantity"]),
        # Missing unit (should fail unit)
        ({"customer_name": "Danish", "delivery_address": "Here", "items": [{"name": "15 tide sarf", "quantity": 15, "unit": None, "price": 0.0}]}, ["unit"]),
    ]
    
    for card_data, expected_missing in val_tests:
        total += 1
        res = validate_action_card(card_data, "test")
        missing = res.get("missing_fields", [])
        
        # Check if expected missing fields match actual missing fields
        missing_match = set(expected_missing).issubset(set(missing)) and len(expected_missing) > 0
        
        if not expected_missing and not missing:
            print(f"  [PASS] Valid card handled correctly: {card_data}")
            passed += 1
        elif expected_missing and missing_match:
            print(f"  [PASS] Caught missing fields {expected_missing} correctly.")
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

    # 10. ONE-CALL LLM MOCK TESTS (DEVANAGARI, FAILURES, EDGE CASES)
    print("\n10. One-Call LLM Mock Tests (Edge Cases):")
    from unittest.mock import patch, MagicMock
    from app.services.gemini import GeminiService
    from app.config.settings import settings
    
    # Temporarily set flag to True for testing
    original_flag = getattr(settings, "ENABLE_LLM_TRANSLITERATION", False)
    
    # Helpers for mocking
    def get_mock_client(response_text=None, error=None):
        mock_response = MagicMock()
        mock_response.text = response_text
        
        mock_client = MagicMock()
        if error:
            mock_client.models.generate_content.side_effect = error
        else:
            mock_client.models.generate_content.return_value = mock_response
        return mock_client

    # Case A: Flag enabled, Devanagari
    settings.ENABLE_LLM_TRANSLITERATION = True
    dev_transcript = "कल 5:30 baje Gupta Store mein 5 kilo आलू bhejna"
    good_json = """
    {
      "transcript_normalized": "kal 5:30 baje Gupta Store mein 5 kilo aloo bhejna",
      "metadata": {
        "normalizer_changes": ["आलू -> aloo"]
      },
      "cards": [{"type": "ORDER", "customer_name": "Gupta Store", "delivery_time_raw": "kal 5:30 baje", "items": [{"name": "aloo", "quantity": "5", "unit": "kilo"}]}]
    }
    """
    with patch('google.genai.Client', return_value=get_mock_client(good_json)):
        res = asyncio.run(GeminiService.extract_order_details(dev_transcript))
        if res.get("metadata", {}).get("transcript_normalized") == "kal 5:30 baje Gupta Store mein 5 kilo aloo bhejna":
            print("  [PASS] Flag enabled with Devanagari: outputs transcript_normalized correctly.")
            passed += 1
        else: print("  [FAIL] Flag enabled Devanagari.")
        total += 1
        
        if res.get("metadata", {}).get("normalizer_changes") == ["आलू -> aloo"]:
            print("  [PASS] normalizer_changes matches actual transformation.")
            passed += 1
        else: print("  [FAIL] normalizer_changes mismatch.")
        total += 1

    # Case B: Flag disabled, Devanagari
    settings.ENABLE_LLM_TRANSLITERATION = False
    flag_disabled_json = f"""
    {{
      "transcript_normalized": "{dev_transcript}",
      "cards": [{{"type": "ORDER", "customer_name": "Gupta Store", "delivery_time_raw": "kal 5:30 baje", "items": [{{"name": "aloo", "quantity": "5", "unit": "kilo"}}]}}]
    }}
    """
    with patch('google.genai.Client', return_value=get_mock_client(flag_disabled_json)): # LLM ignored translit rules
        res = asyncio.run(GeminiService.extract_order_details(dev_transcript))
        if res.get("metadata", {}).get("transcript_normalized") == dev_transcript:
            print("  [PASS] Flag disabled with Devanagari: defaults to original transcript.")
            passed += 1
        else: print(f"  [FAIL] Flag disabled Devanagari: {res.get('metadata')}")
        total += 1

    # Case C: Roman transcript remains unaffected
    settings.ENABLE_LLM_TRANSLITERATION = True
    roman_transcript = "5 kilo aloo"
    with patch('google.genai.Client', return_value=get_mock_client("""{"cards": [{"items": [{"name": "aloo", "quantity": "5", "unit": "kg"}]}]}""")):
        res = asyncio.run(GeminiService.extract_order_details(roman_transcript))
        if res.get("metadata", {}).get("transcript_normalized") == roman_transcript and not res.get("metadata", {}).get("normalization_used"):
            print("  [PASS] Roman transcript remains unaffected.")
            passed += 1
        else: print("  [FAIL] Roman transcript modified.")
        total += 1

    # Case D: Malformed JSON Fallback
    with patch('google.genai.Client', return_value=get_mock_client("malformed { json")):
        res = asyncio.run(GeminiService.extract_order_details(dev_transcript))
        if "customer_name" in res:
            print("  [PASS] Malformed JSON safely falls back to deterministic/Nasir parser.")
            passed += 1
        else: print("  [FAIL] Malformed JSON crashed.")
        total += 1

    # Case E: Missing transcript_normalized fallback
    missing_norm_json = """{"cards": [{"type": "ORDER", "customer_name": "Test", "items": [{"name": "A", "quantity": "1"}]}]}"""
    with patch('google.genai.Client', return_value=get_mock_client(missing_norm_json)):
        res = asyncio.run(GeminiService.extract_order_details(dev_transcript))
        if res.get("metadata", {}).get("transcript_normalized") == dev_transcript:
            print("  [PASS] Missing transcript_normalized safely falls back to original.")
            passed += 1
        else: print("  [FAIL] Missing transcript_normalized failed.")
        total += 1

    # Case F: Missing cards
    missing_cards_json = """{"transcript_normalized": "test"}"""
    with patch('google.genai.Client', return_value=get_mock_client(missing_cards_json)):
        res = asyncio.run(GeminiService.extract_order_details(dev_transcript))
        if res["type"] == "ORDER": # Fallback created a card
            print("  [PASS] Missing cards safely handled.")
            passed += 1
        else: print("  [FAIL] Missing cards failed.")
        total += 1
        
    # Case G: 429/503 API Fallback Exception
    class MockException(Exception): pass
    err = MockException("503 UNAVAILABLE")
    with patch('google.genai.Client', return_value=get_mock_client(error=err)):
        try:
            asyncio.run(GeminiService.extract_order_details(dev_transcript))
            print("  [FAIL] Expected 503 to raise RuntimeError.")
        except RuntimeError as e:
            if "failed" in str(e).lower() or "quota" in str(e).lower():
                print("  [PASS] 503 Exception gracefully raised RuntimeError without crashing.")
                passed += 1
        total += 1
        
    # Case H: Customer Name & Time read from primary_card
    with patch('google.genai.Client', return_value=get_mock_client(good_json)):
        res = asyncio.run(GeminiService.extract_order_details(dev_transcript))
        if res["customer_name"] == "Gupta Store" and res["delivery_time_raw"] == "kal 5:30 baje":
            print("  [PASS] customer_name and delivery_time read correctly from primary_card.")
            passed += 1
        else: print("  [FAIL] failed to read from primary_card.")
        total += 1
        
    # Case I: One-call response preserves metadata fields
    with patch('google.genai.Client', return_value=get_mock_client(good_json)):
        res = asyncio.run(GeminiService.extract_order_details(dev_transcript))
        meta = res.get("metadata", {})
        if all(k in meta for k in ["transcript_original", "transcript_normalized", "stt_provider", "extraction_provider", "pipeline"]) and res["items"][0]["quantity"] == 5.0:
            print("  [PASS] Metadata preserved, original quantities/names intact.")
            passed += 1
        else: print("  [FAIL] Metadata missing fields.")
        total += 1

    settings.ENABLE_LLM_TRANSLITERATION = original_flag
        
    print(f"\nFinal -> Total: {total}, Passed: {passed}, Failed: {total - passed}")

if __name__ == "__main__":
    run_tests()

