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
        ("kal 5 baje, nahi aaj 8 baje", f"{today_date} 8:00", "AM/PM ambiguity detected. Please confirm."),
        ("kal sade 8", f"{tomorrow_date} 8:30", "AM/PM ambiguity detected. Please confirm."),
        ("sawa chhe", None, "Missing specific day"),
        ("paune 5", None, "Missing specific day"),
        ("dhai baje", None, "Missing specific day"),
        ("kal 10:15 pe", f"{tomorrow_date} 10:15", "AM/PM ambiguity detected. Please confirm."),
        ("kal 5:30 baje", f"{tomorrow_date} 5:30", "AM/PM ambiguity detected. Please confirm."),
        ("kal aisa karna 8:30 baje", f"{tomorrow_date} 8:30", "AM/PM ambiguity detected. Please confirm."),
        ("kalle esa karna 5:30 baje", f"{tomorrow_date} 5:30", "Interpreted 'kalle' as 'kal'"),
        ("kal ka order cancel karo, aaj 5 baje naya bhejna", f"{today_date} 5:00", "AM/PM ambiguity detected. Please confirm."),
        ("5:30 baje bhejna", None, "Missing specific day"),
        ("kalle", None, "Uncertain delivery time"), # unrelated kalle without clock
        ("kal 5:30 raat ko", f"{tomorrow_date} 5:30 PM", None),
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
        ("aadha kilo", 0.5, "kg"),
        ("dhai kilo", 2.5, "kg"),
        ("sawa kilo", 1.25, "kg"),
        ("paanch packet", 5.0, "packet"),
        ("sawa 2 litre", 2.25, "litre"),
        ("saade paanch kilo", 5.5, "kg"),
        ("dhai litre", 2.5, "litre"),
        ("sare saath kilo", 7.5, "kg"),
        ("do kilo", 2.0, "kg"),
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
                cust_name = name_match.group(1).strip()
        if cust_name and cust_name != "Unknown":
            cust_name = re.sub(r'(?:\s+(?:rahega|likhna|likh\s*dena|likhdo|rakhna|karna|bhejna|dena|hai|theek\s*hai))+$', '', cust_name, flags=re.IGNORECASE).strip()
            cust_name = cust_name.title()
        return cust_name

    name_cleanup_tests = [
        ("unka naam Danish Likhna", "Danish"),
        ("naam danish likhna", "Danish"),
        ("party ka naam Ram hai theek hai", "Ram"),
        ("naam danish rahega", "Danish")
    ]
    for transcript, expected in name_cleanup_tests:
        cleaned = mock_extract_name(transcript)
        if cleaned == expected:
            print(f"  [PASS] '{transcript}' -> '{cleaned}'")
            passed += 1
        else:
            print(f"  [FAIL] '{transcript}' -> '{cleaned}' (Expected '{expected}')")
        total += 1

    # 8b. ADDRESS FORMATTING PARSING
    print("\n8b. Address Formatting Parsing:")
    def mock_format_address(raw_delivery_address):
        clean_address = str(raw_delivery_address).strip()
        if clean_address:
            clean_address = clean_address.title()
            locality_map = {
                "Shahin Bagh": "Shaheen Bagh",
                "Shainbag": "Shaheen Bagh",
                "Batla House": "Batla House",
                "Okhla": "Okhla",
                "Jamia Nagar": "Jamia Nagar"
            }
            for k, v in locality_map.items():
                if k.lower() in clean_address.lower():
                    clean_address = re.sub(re.escape(k), v, clean_address, flags=re.IGNORECASE)
                    if not re.search(r',\s*' + re.escape(v), clean_address, flags=re.IGNORECASE):
                        clean_address = re.sub(r'\s+' + re.escape(v), f", {v}", clean_address, flags=re.IGNORECASE)
            
            clean_address = re.sub(r'\s*,\s*', ', ', clean_address).strip(', ')
        return clean_address

    address_format_tests = [
        ("gupta house shahin bagh", "Gupta House, Shaheen Bagh"),
        ("gupta house, shahin bagh", "Gupta House, Shaheen Bagh"),
        ("okhla", "Okhla"),
        ("milan kalyan mandap jamia nagar", "Milan Kalyan Mandap, Jamia Nagar"),
        ("Gupta House Shainbag Batla House", "Gupta House, Shaheen Bagh, Batla House")
    ]
    for raw_addr, expected in address_format_tests:
        cleaned = mock_format_address(raw_addr)
        if cleaned == expected:
            print(f"  [PASS] '{raw_addr}' -> '{cleaned}'")
            passed += 1
        else:
            print(f"  [FAIL] '{raw_addr}' -> '{cleaned}' (Expected '{expected}')")
        total += 1

    # 8c. PRODUCT NAME CLEANUP PARSING
    print("\n8c. Product Name Cleanup Parsing:")
    from app.services.gemini import GeminiService

    product_cleanup_tests = [
        ("sarf ka", "sarf"),
        ("surf ka packet", "surf"),
        ("doodh ki theli", "doodh"),
        ("chai patti ka packet", "chai patti"),
        ("parle g ka packet", "parle g"),
        ("lal sarf wala", "lal sarf"),
        ("10 rupiya wala parle g", "10 rupiya wala parle g"),
        ("surf ka packet wala", "surf"),
        ("parle ji ka packet 10 wala", "parle ji 10 wala")
    ]
    for raw_prod, expected in product_cleanup_tests:
        cleaned = GeminiService.clean_product_name(raw_prod)
        if cleaned == expected:
            print(f"  [PASS] '{raw_prod}' -> '{cleaned}'")
            passed += 1
        else:
            print(f"  [FAIL] '{raw_prod}' -> '{cleaned}' (Expected '{expected}')")
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
        ),
        # 5 kg aata + 5 kg aata aur jod dena = 10 kg
        (
            [{"name": "aata", "quantity": 5, "unit": "kg"}, {"name": "aata", "quantity": 5, "unit": "kg"}],
            [{"name": "aata", "quantity": 10, "unit": "kg"}]
        ),
        # 5 kg chini + 10 kg chini aur jod dena + 10 kg sugar aur jod dena = 25 kg sugar
        # (Assuming canonical resolution mapped "chini" and "sugar" to "sugar")
        (
            [
                {"name": "sugar", "quantity": 5, "unit": "kg", "raw_name": "chini"},
                {"name": "sugar", "quantity": 10, "unit": "kg", "raw_name": "chini"},
                {"name": "sugar", "quantity": 10, "unit": "kg", "raw_name": "sugar"}
            ],
            [{"name": "sugar", "quantity": 25, "unit": "kg", "raw_name": "chini"}] # uses raw_name of the first one
        ),
        # 5 kg cheeni + 10 kg cheeni aur jod dena = 15 kg sugar
        (
            [{"name": "cheeni", "quantity": 5, "unit": "kg"}, {"name": "cheeni", "quantity": 10, "unit": "kg"}],
            [{"name": "cheeni", "quantity": 15, "unit": "kg"}]
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
        "model_normalizer_notes": ["आलू -> aloo"]
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

        if res.get("metadata", {}).get("model_normalizer_notes") == ["आलू -> aloo"]:
            print("  [PASS] model_normalizer_notes matches actual transformation.")
            passed += 1
        else: print("  [FAIL] model_normalizer_notes mismatch.")
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

    # Case J: Full Offline Regression Test (Production Safety)
    regression_transcript = "कल ऐसा करना साढ़े पाँच बजे, नहीं नहीं साढ़े आठ बजे ओखला विहार शाहीन बाग में 15 किलो आलू 5 किलो टमाटर 50 किलो चीनी 50 किलो बैंगन 15 किलो नमकीन और ek tight surf add karo, wait tight cancel kar dena aur 10 kilo aloo 10 kilo tamatar add karna aur naam Danish rahega."
    regression_json = """
    {
      "transcript_normalized": "kal aisa karna saade paanch baje, nahi nahi saade aath baje Okhla Vihar Shaheen Bagh mein 15 kilo aloo 5 kilo tamatar 50 kilo chini 50 kilo baingan 15 kilo namkeen aur ek tight surf add karo, wait tight cancel kar dena aur 10 kilo aloo 10 kilo tamatar add karna aur naam Danish rahega.",
      "metadata": {
        "model_normalizer_notes": [
          "साढ़े पाँच -> saade paanch",
          "साढ़े आठ -> saade aath",
          "पंद्रह -> pandrah"
        ],
        "cancelled_items": [{"name": "tight surf", "quantity": "1", "unit": ""}]
      },
      "cards": [
        {
          "type": "ORDER",
          "customer_name": "Danish",
          "delivery_address": "Okhla Vihar Shaheen Bagh",
          "delivery_time_raw": "kal saade paanch baje, nahi nahi saade aath baje",
          "items": [
            {"name": "aloo", "quantity": "15", "unit": "kilo"},
            {"name": "tamatar", "quantity": "5", "unit": "kilo"},
            {"name": "chini", "quantity": "50", "unit": "kilo"},
            {"name": "baingan", "quantity": "50", "unit": "kilo"},
            {"name": "namkeen", "quantity": "15", "unit": "kilo"},
            {"name": "tight surf", "quantity": "1", "unit": ""},
            {"name": "aloo", "quantity": "10", "unit": "kilo"},
            {"name": "tamatar", "quantity": "10", "unit": "kilo"}
          ]
        }
      ]
    }
    """
    with patch('google.genai.Client', return_value=get_mock_client(regression_json)):
        res = asyncio.run(GeminiService.extract_order_details(regression_transcript))

        # Verify customer, address, aloo qty
        if res.get("customer_name") == "Danish" and res.get("delivery_address") == "Okhla Vihar Shaheen Bagh":
            print("  [PASS] Full Regression: Customer and address preserved.")
            passed += 1
        else: print(f"  [FAIL] Full Regression: Customer/address wrong: {res}")
        total += 1

        # Verify Aloo, Tamatar, Chini, Baingan, Namkeen aggregation
        aloo_item = next((i for i in res["items"] if i["name"] == "aloo"), None)
        tamatar_item = next((i for i in res["items"] if i["name"] == "tamatar"), None)
        chini_item = next((i for i in res["items"] if i["name"] == "chini"), None)
        baingan_item = next((i for i in res["items"] if i["name"] == "baingan"), None)
        namkeen_item = next((i for i in res["items"] if i["name"] == "namkeen"), None)

        if (aloo_item and aloo_item["quantity"] == 25 and
            tamatar_item and tamatar_item["quantity"] == 15 and
            chini_item and chini_item["quantity"] == 50 and
            baingan_item and baingan_item["quantity"] == 50 and
            namkeen_item and namkeen_item["quantity"] == 15):
            print("  [PASS] Full Regression: Aggregated qtys (aloo 25, tamatar 15, chini 50, baingan 50, namkeen 15) correct.")
            passed += 1
        else: print(f"  [FAIL] Full Regression: Qtys incorrect. Items: {res['items']}")
        total += 1

        # Corrected time handling & day preserved & AM/PM warning
        if "2026" in str(res["delivery_time_normalized"]) and "8:30" in str(res["delivery_time_normalized"]):
            print("  [PASS] Full Regression: Time mapped to 8:30 and day preserved.")
            passed += 1
        else: print(f"  [FAIL] Full Regression: Time parsing failed: {res['delivery_time_normalized']}")
        total += 1

        if "AM/PM ambiguity" in str(res["delivery_time_warning"]):
            print("  [PASS] Full Regression: AM/PM ambiguity surfaced.")
            passed += 1
        else: print(f"  [FAIL] Full Regression: No AM/PM warning. Got: {res['delivery_time_warning']}")
        total += 1

        # Cancelled tight surf is not active
        if not any("tight surf" in i["name"] for i in res["items"]) and res["metadata"]["cancelled_items"]:
            print("  [PASS] Full Regression: Cancelled item not active, but present in metadata.")
            passed += 1
        else: print("  [FAIL] Full Regression: Cancellation logic failed.")
        total += 1

        # Risks remain
        if "cancellation" in res["risk_flags"] and "large_quantity" in res["risk_flags"]:
            print("  [PASS] Full Regression: Risks remain (cancellation, large_quantity).")
            passed += 1
        else: print(f"  [FAIL] Full Regression: Risks missing. Got: {res['risk_flags']}")
        total += 1

        # Truthful normalization metadata
        if "पंद्रह -> pandrah" in res["metadata"]["model_normalizer_notes"]:
            print("  [PASS] Full Regression: Truthful normalization notes.")
            passed += 1
        else: print("  [FAIL] Full Regression: Truthful normalization missing.")
        total += 1

        # Unique missing_fields
        if len(res["missing_fields"]) == len(set(res["missing_fields"])):
            print("  [PASS] Full Regression: missing_fields are unique.")
            passed += 1
        else: print("  [FAIL] Full Regression: missing_fields not unique.")
        total += 1

        # Irrelevant matches absent (aloo should not have possible matches because cutoff is high)
        if not aloo_item["possible_matches"]:
            print("  [PASS] Full Regression: Irrelevant possible matches absent.")
            passed += 1
        else: print(f"  [FAIL] Full Regression: Irrelevant matches exist: {aloo_item['possible_matches']}")
        total += 1

    # Test Delivery Time Enrichment
    print("\n11. Delivery Time Enrichment:")

    # Mock primary_card and transcript
    async def mock_time_enrichment(raw_llm_time, transcript):
        class MockResponse:
            def __init__(self):
                self.text = f'{{"cards": [{{"delivery_time_raw": "{raw_llm_time}"}}], "transcript_normalized": "{transcript}"}}'

        from google.genai import types
        import unittest.mock as mock

        with mock.patch("app.services.gemini.genai.Client") as MockClient:
            mock_client_instance = MockClient.return_value
            mock_client_instance.models.generate_content.return_value = MockResponse()

            # Since extract_order_details needs API key
            settings.GEMINI_API_KEY = "dummy"
            res = await GeminiService.extract_order_details(transcript)
            return res

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    res1 = loop.run_until_complete(mock_time_enrichment("5 baje", "kal aisa karna 5 baje bhej dena"))
    if res1["delivery_time_raw"] == "kal aisa karna 5 baje" or "kal" in res1["delivery_time_raw"]:
        print(f"  [PASS] 'kal 5 baje' recovery: {res1['delivery_time_raw']}")
        passed += 1
    else:
        print(f"  [FAIL] 'kal 5 baje' recovery failed, got: {res1['delivery_time_raw']}")
    total += 1

    res2 = loop.run_until_complete(mock_time_enrichment("5 baje", "kal 5 baje bhej dena nahi aaj 8 baje bhej dena"))
    if "aaj" in res2["delivery_time_raw"] and "8 baje" in res2["delivery_time_raw"]:
        print(f"  [PASS] 'aaj 8 baje' correction recovery: {res2['delivery_time_raw']}")
        passed += 1
    else:
        print(f"  [FAIL] 'aaj 8 baje' correction recovery failed, got: {res2['delivery_time_raw']}")
    total += 1

    print("\n12. Payment Method Hallucination Check:")
    async def mock_payment_extraction(raw_payment_method, transcript):
        class MockResponse:
            def __init__(self):
                self.text = f'{{"cards": [{{"payment_method": "{raw_payment_method}"}}], "transcript_normalized": "{transcript}"}}'

        from google.genai import types
        import unittest.mock as mock

        with mock.patch("app.services.gemini.genai.Client") as MockClient:
            mock_client_instance = MockClient.return_value
            mock_client_instance.models.generate_content.return_value = MockResponse()

            settings.GEMINI_API_KEY = "dummy"
            res = await GeminiService.extract_order_details(transcript)
            return res

    res_pay1 = loop.run_until_complete(mock_payment_extraction("Online", "ek packet sarfexal 10 wala aur ek packet parleji 10 rupiya pack bhej dena"))
    if res_pay1["payment_method"] == "Not Specified":
        print(f"  [PASS] Hallucinated 'Online' reverted to Not Specified (no intent found)")
        passed += 1
    else:
        print(f"  [FAIL] Hallucinated 'Online' not reverted: {res_pay1['payment_method']}")
    total += 1

    res_pay2 = loop.run_until_complete(mock_payment_extraction("Cash", "ek packet parleji 10 rupiya pack bhej dena online payment kar dunga"))
    if res_pay2["payment_method"] == "Online":
        print(f"  [PASS] 'Cash' overridden to 'Online' based on transcript intent 'online payment'")
        passed += 1
    else:
        print(f"  [FAIL] 'Cash' not overridden to 'Online': {res_pay2['payment_method']}")
    total += 1

    res_pay3 = loop.run_until_complete(mock_payment_extraction("Online", "bhaiya sab likh lena udhaar mein"))
    if res_pay3["payment_method"] == "Credit (Udhaar)":
        print(f"  [PASS] 'Online' overridden to 'Credit (Udhaar)' based on transcript intent 'udhaar mein'")
        passed += 1
    else:
        print(f"  [FAIL] 'Online' not overridden to 'Credit (Udhaar)': {res_pay3['payment_method']}")
    total += 1

    res_pay4 = loop.run_until_complete(mock_payment_extraction("Online", "bhaiya nakad le lena"))
    if res_pay4["payment_method"] == "Cash":
        print(f"  [PASS] 'Online' overridden to 'Cash' based on transcript intent 'nakad'")
        passed += 1
    else:
        print(f"  [FAIL] 'Online' not overridden to 'Cash': {res_pay4['payment_method']}")
    total += 1
    # ---------------------------------------------------------
    # CONFIDENCE SCORER TESTS
    # ---------------------------------------------------------
    print("\n--- Testing Confidence Scorer ---")
    from app.services.confidence_scorer import ConfidenceScorer

    def test_scorer(scenario_name, card_data, expected_label, expected_min_score=None):
        nonlocal passed, total
        score, label, reasons = ConfidenceScorer.calculate_confidence(card_data)
        
        success = True
        if label != expected_label:
            print(f"  [FAIL] {scenario_name}: Expected label '{expected_label}', got '{label}' (Score: {score})")
            success = False
        elif expected_min_score is not None and score < expected_min_score:
            print(f"  [FAIL] {scenario_name}: Expected score >= {expected_min_score}, got {score}")
            success = False
            
        if success:
            print(f"  [PASS] {scenario_name} (Score: {score}, Label: {label})")
            passed += 1
        total += 1

    # 1. Perfect card
    perfect_card = {
        "customer_name": "Danish",
        "delivery_address": "Batla House",
        "delivery_time": "2026-06-25 10:00",
        "items": [
            {"name": "atta", "quantity": 5, "unit": "kg", "price": 50},
            {"name": "sugar", "quantity": 2, "unit": "kg", "price": 45}
        ],
        "validation_warnings": [],
        "confidence": 0.95
    }
    test_scorer("Perfect Card -> High", perfect_card, "High", 100)

    # 2. Missing customer
    missing_cust = dict(perfect_card)
    missing_cust["customer_name"] = "unknown"
    test_scorer("Missing Customer -> drops score", missing_cust, "Medium", 80)

    # 3. Missing catalog price
    missing_price = dict(perfect_card)
    missing_price["items"] = [
        {"name": "atta", "quantity": 5, "unit": "kg", "price": 0.0},
        {"name": "sugar", "quantity": 2, "unit": "kg", "price": 45}
    ]
    # -12 for missing price -> 88
    test_scorer("Missing Catalog Price -> drops score", missing_price, "Medium", 88)

    # 4. AM/PM ambiguity
    ampm_card = dict(perfect_card)
    ampm_card["validation_warnings"] = ["AM/PM ambiguity in delivery time surfaced"]
    # -12 for AM/PM -> 88
    test_scorer("AM/PM Ambiguity -> drops score", ampm_card, "Medium", 88)

    # 5. Missing quantity/unit
    missing_qty = dict(perfect_card)
    missing_qty["items"] = [
        {"name": "atta", "unit": "kg", "price": 50}, # no quantity (-20)
    ]
    test_scorer("Missing Quantity -> drops score", missing_qty, "Medium", 80)

    # 6. Empty items -> Low confidence
    empty_items = dict(perfect_card)
    empty_items["items"] = []
    # -40 for empty items -> 60 (Low)
    test_scorer("Empty Items -> Low", empty_items, "Low", 60)
    
    # 7. Low raw LLM confidence (0.5 -> penalty 10)
    low_llm = dict(perfect_card)
    low_llm["confidence"] = 0.5
    # penalty = int((0.8 - 0.5) * 35) = int(10.5) = 10
    # 100 - 10 = 90
    test_scorer("Low LLM Confidence -> score drops", low_llm, "High", 90)

    # 8. Large quantity only -> High
    large_qty_card = dict(perfect_card)
    large_qty_card["validation_warnings"] = ["large_quantity for atta"]
    # 100 - 2 = 98 (High)
    test_scorer("Large Quantity Only -> High", large_qty_card, "High", 98)

    # 9. Combined Risk -> Low
    combined_card = dict(perfect_card)
    combined_card["customer_name"] = "unknown" # -20
    combined_card["delivery_address"] = "" # -20
    combined_card["validation_warnings"] = ["AM/PM ambiguity in delivery time surfaced"] # -12
    combined_card["items"] = [
        {"name": "atta", "quantity": 5, "unit": "kg", "price": 0.0}, # -12
    ]
    # 100 - 20 - 20 - 12 - 12 = 36 (Low)
    test_scorer("Combined Risk -> Low", combined_card, "Low", 36)

    # 10. Mixed Priced and Unpriced Items
    mixed_card = dict(perfect_card)
    mixed_card["items"] = [
        {"name": "atta", "quantity": 5, "unit": "kg", "price": 50},
        {"name": "sugar", "quantity": 5, "unit": "kg", "price": 40},
        {"name": "chawal", "quantity": 5, "unit": "kg", "price": 0},
        {"name": "surf", "quantity": 5, "unit": "kg", "price": 0}
    ]
    # 100 - 12 - 12 = 76 (Medium)
    test_scorer("Mixed Priced/Unpriced -> Medium", mixed_card, "Medium", 76)

    print("\n--- Testing Stale Warning Cleanup (Endpoints Logic) ---")
    extracted_mock = {
        "validation_warnings": ["Ambiguous product 'atta'. No catalog match found.", "Missing quantity for sugar"],
        "customer_name": "Danish",
        "items": []
    }
    
    # Simulate the logic in endpoints.py
    def clean_warnings(extracted, items):
        validation_warnings = extracted.get("validation_warnings", [])
        final_warnings = []
        matched_names = [i.get("raw_name", i.get("name")) for i in items if i.get("resolution_status") in ("matched", "suggested") or (i.get("price") is not None and i.get("price") > 0)]
        for w in validation_warnings:
            if "No catalog match found" in w or "Ambiguous product" in w:
                is_stale = False
                for mn in matched_names:
                    if mn and (f"'{mn}'" in w or f"'{mn.lower()}'" in w.lower()):
                        is_stale = True
                        break
                if is_stale:
                    continue
            final_warnings.append(w)
        return final_warnings

    items_mock = [
        {"name": "atta", "raw_name": "atta", "price": 50, "resolution_status": "matched"}
    ]
    cleaned = clean_warnings(extracted_mock, items_mock)
    if "Ambiguous product 'atta'. No catalog match found." not in cleaned and "Missing quantity for sugar" in cleaned:
        print("  [PASS] Stale catalog warning cleaned up for matched item")
        passed += 1
    else:
        print(f"  [FAIL] Warning cleanup failed: {cleaned}")
    total += 1

    print("\n--- Testing Name Cleanup Numeric Phrase Preservation ---")
    from app.services.gemini import GeminiService
    cleaned_name = GeminiService.clean_product_name("5 rupaye wala toffee ka")
    if cleaned_name == "5 rupaye wala toffee":
        print(f"  [PASS] Numeric variant phrase preserved: {cleaned_name}")
        passed += 1
    else:
        print(f"  [FAIL] Numeric variant phrase not preserved: {cleaned_name}")
    total += 1

if __name__ == "__main__":
    run_tests()
