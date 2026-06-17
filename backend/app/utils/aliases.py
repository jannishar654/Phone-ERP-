import difflib

BUSINESS_ALIASES = {
    "product_aliases": {
        "bada doodh": "Amul Gold Milk",
        "bade doodh ka packet": "Amul Gold Milk",
        "बड़ा दूध": "Amul Gold Milk",
        "बड़े दूध का पैकेट": "Amul Gold Milk",
        "lal surf": "Surf Excel Easy Wash",
        "lal wala surf": "Surf Excel Easy Wash",
        "लाल सर्फ": "Surf Excel Easy Wash",
        "लाल वाला सर्फ": "Surf Excel Easy Wash",
        "surf excel": "Surf Excel Easy Wash",
        "surf excel ka packet": "Surf Excel Easy Wash",
        "सर्फ एक्सेल": "Surf Excel Easy Wash",
        "सर्फ एक्सेल का पैकेट": "Surf Excel Easy Wash",
        "dus wala parle": "Parle-G ₹10 Pack",
        "दस वाला पार्ले": "Parle-G ₹10 Pack",
        "regular maggi": "Maggi 2-Minute Noodles Regular",
        "रेगुलर मैगी": "Maggi 2-Minute Noodles Regular",
        "parle g": "Parle-G",
        "parle-g": "Parle-G",
        "पार्ले जी": "Parle-G",
    },
    "customer_aliases": {
        "jaaneeshaar": "Jannishar",
        "janishar": "Jannishar",
        "jaaneshar": "Jannishar",
        "janeeshar": "Jannishar"
    },
    "units": ["packet", "peti", "carton", "kg", "kilo", "piece", "box", "pcs", "gm", "gram", "litre", "liter", "l", "ml"],
    "risk_terms": ["udhaar", "scheme", "cancel", "replace", "badal", "baad mein", "cancel kar do", "cancel kardo", "jagah"]
}

def normalize_alias(text: str, alias_dict: dict) -> str:
    if not text:
        return text
    lower_text = text.lower().strip()
    
    # 1. Exact Match
    if lower_text in alias_dict:
        return alias_dict[lower_text]
        
    # 2. Fuzzy Match (85% cutoff for safety on names/short words)
    matches = difflib.get_close_matches(lower_text, alias_dict.keys(), n=1, cutoff=0.85)
    if matches:
        return alias_dict[matches[0]]
        
    # 3. No match, return original
    return text.strip()
