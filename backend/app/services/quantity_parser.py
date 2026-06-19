import re
from typing import Optional, Dict, Any

def parse_quantity(raw_text: Optional[str]) -> Dict[str, Any]:
    if not raw_text or not str(raw_text).strip():
        return {
            "quantity": None,
            "unit": None,
            "raw_quantity": "",
            "confidence": 0.0,
            "warning": "Quantity is missing"
        }

    original_text = str(raw_text).strip()
    text = original_text.lower()

    # Extract unit early to separate it from quantity calculation
    # Common units: kilo, kg, liter, litre, ltr, packet, pkt, peti, carton, box, dozen, gram, gm, pouch
    unit_match = re.search(r'\b(kilo|kg|kilogram|liter|litre|ltr|packet|pkt|peti|carton|box|dozen|darjan|gram|gm|pouch|thaili|piece|pc|pcs|bottle|botal|किलो|लीटर|पैकेट|पेटी|दर्जन|ग्राम|पाउच|थैली|पीस|बोतल)\b', text)
    unit_str = unit_match.group(1) if unit_match else None

    # 1. Translate Devanagari numbers to digits
    devanagari_nums = {
        "एक": "1", "दो": "2", "तीन": "3", "चार": "4",
        "पांच": "5", "पाँच": "5",
        "छह": "6", "छ": "6", "छः": "6",
        "सात": "7", "आठ": "8", "नौ": "9", "दस": "10", "ग्यारह": "11", "बारह": "12",
        "आधा": "0.5", "ढाई": "2.5", "सवा": "1.25", "पौने": "0.75", "डेढ़": "1.5", "डेढ़": "1.5"
    }
    for k, v in devanagari_nums.items():
        text = text.replace(k, v)

    # 2. Translate Romanized Hindi numbers to digits (tolerant regex)
    num_patterns = {
        r'\ba+dh+a+\b': "0.5",
        r'\bdh?a+i+\b': "2.5",
        r'\bsa+[vw]a+\b': "1.25",
        r'\bp[ao]+[uwn]*e+\b': "0.75",
        r'\bdh?e+a?dh?\b': "1.5",
        r'\be+k\b': "1",
        r'\bd+o+\b': "2",
        r'\bt+e+n+\b|\bt+i+n+\b': "3",
        r'\bc+h+a+r+\b': "4",
        r'\bp+a+n*c*h+\b': "5",
        r'\bc+h+[eh]+\b': "6",
        r'\bs+a+t+h?\b': "7",
        r'\ba+t+h+\b': "8",
        r'\bn+a+u+\b|\bn+o+\b': "9",
        r'\bd+a+s+\b|\bd+u+s+\b': "10",
        r'\bg+y+a+r+a+h?\b': "11",
        r'\bb+a+r+a+h?\b': "12",
    }
    for pattern, digit in num_patterns.items():
        text = re.sub(pattern, digit, text)

    # 3. Look for explicit fractional combinations (e.g., "sawa 5" -> "5.25")
    # sawa X -> X + 0.25
    def sawa_repl(m):
        return str(float(m.group(1)) + 0.25)
    text = re.sub(r'1\.25\s+(\d+(?:\.\d+)?)', sawa_repl, text)

    # saade/sare X -> X + 0.5 (saade = 0.5 prefix)
    text = re.sub(r'\bs[sh]?a+(?:dh?|r)e+\s+(\d+(?:\.\d+)?)\b', lambda m: str(float(m.group(1)) + 0.5), text)
    text = re.sub(r'साढ़े\s+(\d+(?:\.\d+)?)', lambda m: str(float(m.group(1)) + 0.5), text)
    text = re.sub(r'साढ़े\s+(\d+(?:\.\d+)?)', lambda m: str(float(m.group(1)) + 0.5), text)

    # paune X -> X - 0.25 (paune 5 = 4.75)
    def paune_repl(m):
        val = float(m.group(1))
        if val == 1:
            return "0.75" # paune 1 is 0.75
        return str(val - 0.25)
    text = re.sub(r'0\.75\s+(\d+(?:\.\d+)?)', paune_repl, text)

    from app.services.unit_normalizer import normalize_unit
    unit_str = normalize_unit(unit_str)

    # 4. Extract numeric value with full boundary checks
    quantity = None
    confidence = 0.0
    warning = None

    for match in re.finditer(r'\b\d+(?:\.\d+)?\b', text):
        num_str = match.group()
        start = match.start()
        end = match.end()

        # Look around context
        pre_context = text[max(0, start - 15):start].lower()
        post_context = text[end:end + 15].lower()

        # Reject if part of Rs/rupee price
        if re.search(r'(rs\.?|rupee|rupees|₹|price)\s*$', pre_context):
            continue

        # Reject if product variant like "10 wala"
        if re.match(r'\s*(wala|wali|wale)\b', post_context):
            continue

        try:
            quantity = float(num_str)
            if quantity.is_integer():
                quantity = int(quantity)
            confidence = 0.9
            break # Found a valid quantity
        except ValueError:
            pass

    if quantity is None:
        warning = "Quantity could not be parsed"
        confidence = 0.1

    # Only apply clean_text if a quantity was actually extracted, OR if a unit was found (e.g. "chips ka packet" -> qty None, unit packet, clean_text "chips ka")
    # Wait, the user said: "Only apply cleaned_text when a valid quantity expression was confidently extracted."
    # BUT "chips ka packet -> quantity=None, unit=packet" requires cleaned_text to become "chips ka" to remove the unit?
    # Let's say we only strip numbers if quantity is found. We strip unit if unit is found.
    clean_text = original_text

    if unit_str or quantity is not None:
        if unit_match:
            clean_text = re.sub(r'\b' + re.escape(unit_match.group(1)) + r'\b', '', clean_text, flags=re.IGNORECASE)

        if quantity is not None:
            # Strip common spoken hindi number words explicitly for cleaning
            strip_patterns = [
                r'\ba+dh+a+\b', r'\bdh?a+i+\b', r'\bsa+[vw]a+\b', r'\bp[ao]+[uwn]*e+\b', r'\bdh?e+a?dh?\b',
                r'\be+k\b', r'\bd+o+\b', r'\bt+e+n+\b|\bt+i+n+\b', r'\bc+h+a+r+\b', r'\bp+a+n*c*h+\b',
                r'\bc+h+[eh]+\b', r'\bs+a+t+h?\b', r'\ba+t+h+\b', r'\bn+a+u+\b|\bn+o+\b', r'\bd+a+s+\b|\bd+u+s+\b',
                r'\bg+y+a+r+a+h?\b', r'\bb+a+r+a+h?\b', r'\bs[sh]?a+(?:dh?|r)e+\b', r'\b\d+(?:\.\d+)?\b'
            ]
            for sp in strip_patterns:
                clean_text = re.sub(sp, '', clean_text, flags=re.IGNORECASE)

            for dev_num in list(devanagari_nums.keys()) + ['साढ़े', 'साढ़े']:
                clean_text = clean_text.replace(dev_num, '')

        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    else:
        # If neither quantity nor unit was extracted, don't clean it
        clean_text = original_text

    return {
        "quantity": quantity,
        "unit": unit_str,
        "raw_quantity": original_text,
        "confidence": confidence,
        "warning": warning,
        "cleaned_text": clean_text if clean_text else original_text
    }
