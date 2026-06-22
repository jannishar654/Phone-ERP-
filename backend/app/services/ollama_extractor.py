import json
import logging
import re
import asyncio
import aiohttp
from app.services.gemini import GeminiService
from app.utils.aliases import BUSINESS_ALIASES, normalize_alias
from app.services.business_memory import business_memory
from app.services.time_parser import parse_delivery_time
from app.services.action_card_validator import validate_action_card

logger = logging.getLogger(__name__)

class OllamaService:
    @staticmethod
    async def extract_order_details(transcript_text: str) -> dict:
        """Extract structured order details from transcript using local Ollama (Qwen 2.5 7B)."""
        transcript = transcript_text.strip()
        if not transcript:
            raise ValueError("Transcript is empty.")

        # Exactly the same prompt as GeminiService for guaranteed structural parity
        prompt = (
            "You are an expert grocery order extraction AI.\n"
            "Your task is to extract structured entities from a customer transcript.\n"
            "IMPORTANT RULES:\n"
            "1. ALL VALUES MUST BE IN ENGLISH LETTERS (ROMANIZED HINGLISH). DO NOT OUTPUT ANY DEVANAGARI/HINDI SCRIPT.\n"
            "2. ISOLATE CORE PRODUCT NAMES: Strictly separate the core product name from its quantity, unit, or packaging type. The `name` field must ONLY contain the core product (e.g., 'doodh', 'aata', 'oil'). NEVER include numbers, units (kilo, liter, gram), or packaging words (packet, thaili, bori, dabba, bottle) in the `name` field.\n"
            "   - Example: 'ek badi thaili doodh ki' -> name: 'bada doodh', quantity: 1, unit: 'thaili'\n"
            "   - Example: '10 kilo aata ka packet' -> name: 'aata', quantity: 10, unit: 'kilo'\n"
            "   - Example: '2 bori chawal' -> name: 'chawal', quantity: 2, unit: 'bori'\n"
            "3. TRANSLITERATE AND STANDARDIZE: Convert Devanagari Hindi into Romanized English letters. Use standard English dictionary spellings for common English words (e.g. 'sugar' instead of 'shugar', 'potato' instead of 'potato/poteto'). For pure Hindi words without English equivalents, use standard Hinglish spelling (e.g. 'aata', 'aaloo').\n"
            "4. SYNTHESIZE FULL ADDRESSES: For `customer_name` and `delivery_address`, NEVER output Devanagari. Transliterate to English EXACTLY as spoken phonetically. DO NOT hallucinate, guess, or \"correct\" location names to different places (e.g., if the user says 'Shaheen Bagh', keep it as 'Shaheen Bagh', do NOT change it to 'Shahi Nagar'). CRITICAL: You must capture the ENTIRE address. If a house name, number, or landmark (e.g., 'Gupta House') is mentioned alongside an area (e.g., 'Batla House'), combine them into a full address (e.g., 'Gupta House, Batla House'). Remove conversational filler like 'ke yahan'.\n"
            "5. EXTRACT FRACTIONAL HINDI TIMES CORRECTLY: If the user speaks fractional Hindi times, accurately convert them to English digital time. For example: 'साढ़े सात' (saadhe saat) -> 7:30, 'सवा पाँच' (sawa paanch) -> 5:15, 'पौने आठ' (paune aath) -> 7:45, 'ढाई' (dhai) -> 2:30, 'डेढ़' (dedh) -> 1:30. Pay close attention to 'साढ़े' which strictly means 30 minutes past the hour.\n"
            "6. CLEAN ITEM NAMES: Remove all conversational action verbs from item names (e.g., 'bhijwa dena', 'de dena', 'pack kar dena', 'le aana'). For example, '15 liter tail bhijwa dena' -> name: 'tail' (or 'oil'), NEVER 'tail bhijwa dena'.\n"
            "7. GROCERY STORE CONTEXT: You are processing orders for an Indian grocery store. Assume all items are standard grocery or household products. If a Devanagari word is difficult to transliterate (e.g., 'चीनी'), aggressively map it to standard grocery vocabulary (e.g., 'chini', 'sugar', 'aata', 'chawal', 'tail', 'sabji'). DO NOT hallucinate strange, non-grocery, or offensive words.\n"
            "8. AGGREGATE DUPLICATES: Listen carefully to the entire transcript. If the user mentions the exact same item multiple times (e.g., '5 kilo chini' and later '10 kilo chini aur'), YOU MUST add the quantities together. Example -> quantity: 15, unit: 'kilo', name: 'chini'. DO NOT drop duplicate mentions.\n"
            "9. NEVER MERGE UNRELATED ITEMS: Do not accidentally glue two completely different products into one name. For example, 'surf excel' is detergent and 'chawal' is rice. If the user says them together, extract them as TWO separate items. NEVER extract 'surf excel chawal'.\n"
            "10. PRESERVE RAW DELIVERY TIME: Extract delivery time exactly as spoken. Preserve words like kal, tomorrow, parso, aaj, subah, shaam, raat, after 8 PM, 5 baje, 10:15 pe. Do not put delivery-time words inside delivery_address. If exact normalized date/time is unclear, keep delivery_time_raw and leave delivery_time_normalized blank. Do not invent missing customer, address, price, quantity, or delivery time.\n"
            "11. EXACT RAW QUANTITY: For the 'quantity' field in items, NEVER convert fractional Hindi words (like dhai, saadhe paanch, sawa 2) into numbers. ALWAYS extract the exact raw words spoken as a STRING (e.g. 'dhai', 'साढ़े पाँच', 'sawa'). Do not do math.\n"
            "Map the extracted data into the following JSON schema:\n"
            "customer_name, customer_phone, delivery_address, delivery_time_raw, items.\n"
            "items must be an array of objects with name, quantity (STRING), unit, price.\n"
            "If a value is not present, use an empty string or 0.\n"
            "Do not include any additional keys.\n\n"
            f"Transcript:\n{transcript}\n"
            "Output only JSON."
        )

        try:
            # We use aiohttp to query the local ollama daemon natively without dependencies
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "qwen2.5:7b",
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {
                            "temperature": 0.1 # low temp for deterministic JSON
                        }
                    },
                    timeout=60.0
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Ollama server returned {response.status}: {await response.text()}")
                    
                    data = await response.json()
                    result_text = data.get("response", "").strip()

            parsed = None
            try:
                parsed = json.loads(result_text)
            except json.JSONDecodeError:
                json_match = re.search(r"\{.*\}", result_text, re.S)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        parsed = None

            if not parsed or not isinstance(parsed, dict):
                logger.warning("Could not parse Ollama extraction output, using fallback parser.")
                return GeminiService._parse_order_fallback(transcript)

        except Exception as error:
            logger.exception(f"Ollama extraction failed: {error}")
            return GeminiService._parse_order_fallback(transcript)

        # Standard processing to match Gemini exactly
        items = parsed.get("items") or []
        if not isinstance(items, list):
            items = []

        normalized_items = []
        for item in items:
            if isinstance(item, dict):
                # --- quantity + unit (new pipeline) ---
                raw_qty = item.get("quantity", "")
                raw_unit = item.get("unit", "")
                
                # If LLM passed a string containing quantity and unit, pipe it to quantity_parser
                from app.services.quantity_parser import parse_quantity
                from app.services.unit_normalizer import normalize_unit
                
                combined_raw = f"{raw_qty} {raw_unit}".strip()
                parsed_qty_data = parse_quantity(combined_raw)
                
                qty = parsed_qty_data["quantity"]
                unit = normalize_unit(parsed_qty_data["unit"] or raw_unit)

                raw_price = item.get("price")
                try:
                    price = float(raw_price) if raw_price not in (None, "", "null", "None") else 0.0
                except (ValueError, TypeError):
                    price = 0.0

                cust_phone = parsed.get("customer_phone", "").strip()
                normalized_name = business_memory.resolve_product(item.get("name", "").strip(), customer_id=cust_phone)
                normalized_items.append({
                    "name": normalized_name,
                    "quantity": qty,
                    "unit": unit,
                    "price": price,
                })

        for item in normalized_items:
            unit_lower = item["unit"].lower().strip()
            if "rupee" in unit_lower or "rs" in unit_lower or "inr" in unit_lower:
                item["price"] = max(item["price"], float(item["quantity"]))
                item["quantity"] = 1
                item["unit"] = ""

        if not normalized_items:
            normalized_items = [{"name": "Unknown Item", "quantity": 1, "unit": "", "price": 0.0}]

        cust_name = parsed.get("customer_name", "").strip()
        normalized_cust = normalize_alias(cust_name, BUSINESS_ALIASES["customer_aliases"])
        
        # Apply deterministic time parsing
        raw_delivery_time = parsed.get("delivery_time_raw", parsed.get("delivery_time", "")).strip()
        time_data = parse_delivery_time(raw_delivery_time)

        # --- Layer 2: LLM Fallback Assist ---
        fallback_payload = {}
        unresolved_items = []
        for i, item in enumerate(normalized_items):
            if item.get("quantity") is None:
                item["raw_quantity_spoken"] = str(items[i].get("quantity", ""))
                unresolved_items.append({
                    "index": i,
                    "raw_name": str(items[i].get("name", "")),
                    "raw_quantity": str(items[i].get("quantity", "")),
                    "raw_unit": str(items[i].get("unit", ""))
                })
                
        if not time_data["normalized"] and raw_delivery_time:
            fallback_payload["unresolved_time"] = raw_delivery_time

        if unresolved_items:
            fallback_payload["unresolved_items"] = unresolved_items

        validation_warnings = []
        if fallback_payload and getattr(settings, "ENABLE_LLM_FALLBACK", False):
            from app.services.llm_normalizer import LLMNormalizer
            logger.info(f"Triggering Layer 2 LLM Normalizer for {len(unresolved_items)} items/time.")
            fixed_data = await LLMNormalizer.fix_messy_fields(fallback_payload)
            
            if "unresolved_time" in fixed_data and fixed_data["unresolved_time"]:
                time_data["normalized"] = fixed_data["unresolved_time"]
                validation_warnings.append("AI Assist used to fix delivery time.")
                
            if "unresolved_items" in fixed_data and isinstance(fixed_data["unresolved_items"], list):
                for fixed_item, orig_unresolved in zip(fixed_data["unresolved_items"], unresolved_items):
                    idx = orig_unresolved["index"]
                    if fixed_item.get("raw_quantity") is not None:
                        normalized_items[idx]["quantity"] = fixed_item["raw_quantity"]
                        validation_warnings.append(f"AI Assist used to parse quantity for '{orig_unresolved['raw_name']}'.")
                    if fixed_item.get("raw_name") and fixed_item.get("raw_name").lower() != orig_unresolved["raw_name"].lower():
                        new_name = business_memory.resolve_product(fixed_item["raw_name"], customer_id=cust_phone)
                        normalized_items[idx]["name"] = new_name
                        validation_warnings.append(f"AI Assist corrected spelling for '{orig_unresolved['raw_name']}'.")

        final_data = {
            "customer_name": normalized_cust,
            "customer_phone": parsed.get("customer_phone", "").strip(),
            "delivery_address": parsed.get("delivery_address", "").strip(),
            "delivery_time_raw": raw_delivery_time,
            "delivery_time_normalized": time_data["normalized"],
            "delivery_time_confidence": time_data["confidence"],
            "delivery_time_warning": time_data["warning"],
            "delivery_time": time_data["normalized"] or raw_delivery_time, # fallback for UI compatibility
            "items": normalized_items,
            "validation_warnings": validation_warnings
        }

        # Apply deterministic action card validation
        from app.services.risk_detector import detect_risks
        risk_data = detect_risks(transcript, normalized_items)
        
        # Merge risk detector warnings to our main validation_warnings list
        risk_warnings = risk_data.pop("validation_warnings", [])
        validation_warnings.extend(risk_warnings)

        final_data.update(risk_data)
        
        validation_data = validate_action_card(final_data, transcript)
        
        # Merge our local validation_warnings (AI Fallbacks, payment overrides, risk details)
        # into the action card validation warnings
        if "validation_warnings" not in validation_data:
            validation_data["validation_warnings"] = []
        validation_data["validation_warnings"].extend(final_data.pop("validation_warnings", []))
        
        final_data.update(validation_data)

        return final_data
