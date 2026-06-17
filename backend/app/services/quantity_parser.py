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

    text = str(raw_text).lower().strip()
    original_text = text
    
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
    
    # 4. Extract numeric value
    qty_match = re.search(r'(\d+(?:\.\d+)?)', text)
    
    quantity = None
    confidence = 0.0
    warning = None
    
    if qty_match:
        try:
            quantity = float(qty_match.group(1))
            if quantity.is_integer():
                quantity = int(quantity)
            confidence = 0.9
        except ValueError:
            quantity = None
            
    if quantity is None:
        warning = "Quantity could not be parsed"
        confidence = 0.1
        
    return {
        "quantity": quantity,
        "unit": unit_str,
        "raw_quantity": original_text,
        "confidence": confidence,
        "warning": warning
    }
