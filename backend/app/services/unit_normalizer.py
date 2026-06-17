import re
from typing import Optional

def normalize_unit(raw_unit: Optional[str]) -> Optional[str]:
    if not raw_unit or not str(raw_unit).strip():
        return None
        
    text = str(raw_unit).lower().strip()
    
    # Standard mappings
    if re.search(r'\b(kilo|kg|kilogram|किलो|kgs)\b', text):
        return "kg"
    elif re.search(r'\b(liter|litre|ltr|लीटर)\b', text):
        return "litre"
    elif re.search(r'\b(packet|pkt|पैकेट)\b', text):
        return "packet"
    elif re.search(r'\b(peti|carton|box|पेटी)\b', text):
        return "carton"
    elif re.search(r'\b(dozen|darjan|दर्जन)\b', text):
        return "dozen"
    elif re.search(r'\b(gram|gm|ग्राम)\b', text):
        return "gram"
    elif re.search(r'\b(pouch|पाउच)\b', text):
        return "pouch"
    elif re.search(r'\b(thaili|थैली)\b', text):
        return "thaili"
    elif re.search(r'\b(piece|pc|pcs|पीस)\b', text):
        return "piece"
    elif re.search(r'\b(bottle|botal|बोतल)\b', text):
        return "bottle"
        
    return text
