import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

def parse_delivery_time(raw_text: Optional[str], reference_datetime: Optional[datetime] = None) -> Dict[str, Any]:
    if reference_datetime is None:
        reference_datetime = datetime.now()

    if not raw_text or not str(raw_text).strip():
        return {
            "raw": None,
            "normalized": None,
            "confidence": 0.0,
            "warning": None
        }

    text = str(raw_text).lower().strip()
    
    normalized = None
    confidence = 0.0
    warning = None

    # Base date calculations
    today = reference_datetime.date()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    # 1. Translate Devanagari numbers to digits
    devanagari_nums = {
        "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5", "छह": "6", "छ": "6", 
        "सात": "7", "आठ": "8", "नौ": "9", "दस": "10", "ग्यारह": "11", "बारह": "12"
    }
    for k, v in devanagari_nums.items():
        text = text.replace(k, v)
        
    # 2. Translate Romanized Hindi numbers to digits (tolerant regex)
    num_patterns = {
        r'\be+k\b': "1",
        r'\bd+o+\b': "2",
        r'\bt+e+n+\b|\bt+i+n+\b': "3",
        r'\bc+h+a+r+\b': "4",
        r'\bp+a+n*c*h+\b': "5",  # e.g., paanch, panch, paach
        r'\bc+h+[eh]+\b': "6",  # e.g., chhe, che
        r'\bs+a+t+\b': "7",
        r'\ba+t+h+\b': "8",
        r'\bn+a+u+\b|\bn+o+\b': "9",
        r'\bd+a+s+\b|\bd+u+s+\b': "10",
        r'\bg+y+a+r+a+h?\b': "11",
        r'\bb+a+r+a+h?\b': "12",
    }
    for pattern, digit in num_patterns.items():
        text = re.sub(pattern, digit, text)

    # 3. Apply fractional prefixes mathematically
    # "saade X" -> "X:30" (matches sade, saade, sadhe, saadhe, shaade)
    text = re.sub(r'\bs[sh]?a+dh?e+\s+(\d{1,2})\b', lambda m: f"{m.group(1)}:30", text)
    text = re.sub(r'साढ़े\s+(\d{1,2})', lambda m: f"{m.group(1)}:30", text)
    text = re.sub(r'साढ़े\s+(\d{1,2})', lambda m: f"{m.group(1)}:30", text)

    # "paune X" -> "(X-1):45" (matches pone, paune, pawne, etc.)
    def paune_repl(m):
        val = int(m.group(1))
        hour = 12 if val == 1 else val - 1
        return f"{hour}:45"
    text = re.sub(r'\bp[ao]+[uwn]*e+\s+(\d{1,2})\b', paune_repl, text)
    text = re.sub(r'पौने\s+(\d{1,2})', paune_repl, text)

    # "sawa X" -> "X:15" (matches sawa, sava, sawaa, etc.)
    text = re.sub(r'\bsa+[vw]a+\s+(\d{1,2})\b', lambda m: f"{m.group(1)}:15", text)
    text = re.sub(r'सवा\s+(\d{1,2})', lambda m: f"{m.group(1)}:15", text)
    
    # 4. Handle dedh (1:30) and dhai (2:30) explicitly
    text = re.sub(r'\bdh?e+a?dh?\b|डेढ़|डेढ़', '1:30', text)
    text = re.sub(r'\bdh?a+i+\b|ढाई', '2:30', text)

    # Find all exact time matches
    time_matches = list(re.finditer(r'(\d{1,2}:\d{2}(?:\s*(?:am|pm|baje|ke baad|after|बजे|pe|पे))?|\d{1,2}\s+(?:am|pm|baje|ke baad|after|बजे|pe|पे))', text))
    
    exact_time_match = time_matches[-1] if time_matches else None
    first_time_match = time_matches[0] if time_matches else None

    # Determine the day
    date_str = None
    has_kalle = False
    
    if exact_time_match: # Use the final time match to anchor the day
        clock_start = exact_time_match.start()
        # Find all day matches
        days = list(re.finditer(r'\b(kal|kl|kall|kalle|tomorrow|कल|aaj|today|आज|parso|day after tomorrow|परसो)\b', text))
        if days:
            # Find nearest day before or after the clock
            # A simple heuristic: find the one closest to clock_start
            closest_day = min(days, key=lambda d: abs(d.start() - clock_start))
            day_text = closest_day.group(0)
            
            if re.search(r'\b(kal|kl|kall|kalle|tomorrow|कल)\b', day_text):
                date_str = tomorrow.strftime("%Y-%m-%d")
                if re.search(r'\b(kall|kalle)\b', day_text):
                    has_kalle = True
            elif re.search(r'\b(aaj|today|आज)\b', day_text):
                date_str = today.strftime("%Y-%m-%d")
            elif re.search(r'\b(parso|day after tomorrow|परसो)\b', day_text):
                date_str = day_after.strftime("%Y-%m-%d")
    
    if not date_str:
        # Fallback to simple matching if no clock or day wasn't near clock
        has_kalle = bool(re.search(r'\b(kall|kalle)\b', text)) and exact_time_match
        has_kal = bool(re.search(r'\b(kal|kl|tomorrow|कल)\b', text)) or has_kalle
        has_aaj = bool(re.search(r'\b(aaj|today|आज)\b', text))
        has_parso = bool(re.search(r'\b(parso|day after tomorrow|परसो)\b', text))
        
        if has_kal:
            date_str = tomorrow.strftime("%Y-%m-%d")
        elif has_aaj:
            date_str = today.strftime("%Y-%m-%d")
        elif has_parso:
            date_str = day_after.strftime("%Y-%m-%d")

    has_subah = bool(re.search(r'\b(subah|morning|सुबह)\b', text))
    has_dopahar = bool(re.search(r'\b(dopahar|afternoon|दोपहर)\b', text))
    has_shaam = bool(re.search(r'\b(shaam|evening|शाम)\b', text))
    has_raat = bool(re.search(r'\b(raat|night|रात)\b', text))
    has_din_mein = bool(re.search(r'\b(din me|din mein|din mai|दिन में)\b', text))

    time_str = None
    if exact_time_match:
        time_str = exact_time_match.group(1).strip()
        confidence = 0.9
        time_lower = time_str.lower()
        
        # Clean up trailing words
        clean_time = re.sub(r'\s*(?:baje|ke baad|after|बजे|pe|पे)$', '', time_str, flags=re.IGNORECASE).strip()
        
        # Format bare hours "8" to "8:00"
        time_parts = clean_time.split()
        if ':' not in time_parts[0] and time_parts[0].isdigit():
            time_parts[0] += ":00"
        clean_time = " ".join(time_parts)

        if "am" not in time_lower and "pm" not in time_lower:
            hour = None
            try:
                hour = int(clean_time.split(":")[0])
            except ValueError:
                pass

            if has_raat or has_shaam or has_dopahar:
                time_str = f"{clean_time} PM"
            elif has_subah:
                time_str = f"{clean_time} AM"
            elif has_din_mein and hour is not None and 1 <= hour <= 6:
                time_str = f"{clean_time} PM"
            else:
                time_str = clean_time
                warning = "AM/PM ambiguity detected. Please confirm."
        else:
            time_str = clean_time.upper()
    elif has_subah:
        time_str = "Morning"
        confidence = 0.8
    elif has_dopahar:
        time_str = "Afternoon"
        confidence = 0.8
    elif has_shaam:
        time_str = "Evening"
        confidence = 0.8
    elif has_raat:
        time_str = "Night"
        confidence = 0.8
    
    if date_str and time_str:
        normalized = f"{date_str} {time_str}"
        confidence = max(confidence, 0.9)
    elif date_str:
        normalized = date_str
        confidence = 0.7
        if not warning: warning = "Time needs confirmation"
    elif time_str:
        normalized = None
        confidence = 0.5
        warning = "Missing specific day. Please confirm day."
    else:
        confidence = 0.2
        warning = "Uncertain delivery time, needs confirmation"
        normalized = None

    if has_kalle and exact_time_match:
        if warning:
            warning += " | Interpreted 'kalle' as 'kal'"
        else:
            warning = "Interpreted 'kalle' as 'kal'"

    return {
        "raw": raw_text,
        "normalized": normalized,
        "confidence": confidence,
        "warning": warning
    }
