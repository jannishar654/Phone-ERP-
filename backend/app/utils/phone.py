import re
from typing import Optional


def normalize_phone(phone: str) -> Optional[str]:
    """Normalize WhatsApp identifiers to E.164, defaulting local numbers to India."""
    if not phone or phone.lower().strip() == "skip":
        return None
    cleaned = phone.strip().replace("whatsapp:", "")
    cleaned = re.sub(r"[^\d+]", "", cleaned)
    if re.fullmatch(r"\+\d{8,15}", cleaned):
        return cleaned
    if re.fullmatch(r"91\d{10}", cleaned):
        return f"+{cleaned}"
    if re.fullmatch(r"\d{10}", cleaned):
        return f"+91{cleaned}"
    if re.fullmatch(r"\d{8,15}", cleaned):
        return f"+{cleaned}"
    return None
