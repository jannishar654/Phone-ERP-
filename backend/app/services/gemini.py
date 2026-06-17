import asyncio
import json
import logging
import os
import re
import tempfile

from google import genai
from google.genai import errors
from google.genai import types

from app.config.settings import settings
from app.utils.aliases import BUSINESS_ALIASES, normalize_alias
from app.services.business_memory import business_memory
from app.services.time_parser import parse_delivery_time
from app.services.action_card_validator import validate_action_card

logger = logging.getLogger(__name__)


class GeminiService:

    @staticmethod
    def _detect_audio_format(file_content: bytes, filename: str) -> tuple[str, str]:
        """Return a reliable temporary-file suffix and MIME type."""

        if len(file_content) >= 12 and b"ftyp" in file_content[4:12]:
            return ".m4a", "audio/mp4"

        if file_content.startswith(b"\x1a\x45\xdf\xa3"):
            return ".webm", "audio/webm"

        extension = os.path.splitext(filename)[1].lower()
        formats = {
            ".wav": ("audio/wav", ".wav"),
            ".mp3": ("audio/mpeg", ".mp3"),
            ".m4a": ("audio/mp4", ".m4a"),
            ".mp4": ("audio/mp4", ".mp4"),
            ".ogg": ("audio/ogg", ".ogg"),
            ".webm": ("audio/webm", ".webm"),
        }
        mime_type, suffix = formats.get(extension, ("application/octet-stream", extension or ".bin"))
        return suffix, mime_type

    @staticmethod
    def _clean_transcript(transcript: str) -> str:
        """Remove timeline labels accidentally returned by transcription."""

        timestamp_pattern = r"\b\d{1,2}:\d{2}(?::\d{2})?\b"
        timestamps = re.findall(timestamp_pattern, transcript)

        # A single time can be a real delivery time. Multiple labels, or output
        # beginning at 00:xx, indicate that Gemini generated a timeline.
        if transcript.strip().startswith("00:") or len(timestamps) >= 2:
            transcript = re.sub(timestamp_pattern, " ", transcript)

        return re.sub(r"\s+", " ", transcript).strip()

    @staticmethod
    async def transcribe_audio_file(file_content: bytes, filename: str) -> str:
        """Upload audio to Gemini and return its transcript."""

        if not file_content:
            raise ValueError("Audio file is empty.")

        if (
            not settings.GEMINI_API_KEY
            or settings.GEMINI_API_KEY == "your-gemini-api-key-here"
        ):
            raise ValueError("Gemini API key is not configured.")

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        file_extension, mime_type = GeminiService._detect_audio_format(
            file_content,
            filename,
        )
        temporary_path = None
        uploaded_file = None

        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=file_extension,
            ) as temporary_file:
                temporary_file.write(file_content)
                temporary_path = temporary_file.name

            uploaded_file = await asyncio.to_thread(
                client.files.upload,
                file=temporary_path,
                config=types.UploadFileConfig(
                    mime_type=mime_type,
                    display_name=filename,
                ),
            )

            for _ in range(30):
                uploaded_file = await asyncio.to_thread(
                    client.files.get,
                    name=uploaded_file.name,
                )

                if uploaded_file.state == types.FileState.ACTIVE:
                    break

                if uploaded_file.state == types.FileState.FAILED:
                    raise RuntimeError(
                        f"Gemini failed to process the uploaded audio: {uploaded_file.error}"
                    )

                await asyncio.sleep(1)
            else:
                raise TimeoutError("Gemini audio processing timed out.")

            prompt = """
Transcribe this grocery order exactly as spoken.

The audio may contain English, Hindi, and Hinglish (Romanized Hindi) mixed together.
Preserve Hindi / Hinglish words exactly as spoken. Do not translate Hindi words into English.
Preserve brand names, quantities, pack sizes, units, and customer names.
Do not summarize, correct, or invent extra details.
If any word is not clear, write [unclear] in its place.
Ignore silence and pauses.
Do not include timestamps, duration labels, speaker labels, or numbering.
Return only the words actually spoken by the user.
Return only the transcript text.
"""

            response = None
            models = ("gemini-2.5-flash-lite", "gemini-2.5-flash")

            for model_name in models:
                for attempt in range(3):
                    try:
                        response = await asyncio.to_thread(
                            client.models.generate_content,
                            model=model_name,
                            contents=[uploaded_file, prompt],
                        )
                        break
                    except errors.ServerError as error:
                        if error.code != 503 or attempt == 2:
                            logger.warning(
                                "Gemini model %s unavailable: %s",
                                model_name,
                                error,
                            )
                            break

                        await asyncio.sleep(2 ** attempt)

                if response:
                    break

            if not response:
                raise RuntimeError(
                    "Gemini transcription models are temporarily unavailable. "
                    "Please try again shortly."
                )

            raw_transcript = response.text.strip() if response.text else ""
            transcript = GeminiService._clean_transcript(raw_transcript)

            if not transcript:
                raise ValueError("Gemini returned an empty transcript.")

            return transcript

        except Exception as error:
            logger.exception("Audio transcription failed.")
            raise RuntimeError(
                f"Audio transcription failed: {error}"
            ) from error

        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)

            if uploaded_file:
                try:
                    await asyncio.to_thread(
                        client.files.delete,
                        name=uploaded_file.name,
                    )
                except Exception:
                    logger.warning("Could not delete uploaded Gemini file.")

    @staticmethod
    def _normalize_quantity(quantity_str: str) -> int:
        quantity_map = {
            "ek": 1, "one": 1, "एक": 1,
            "do": 2, "two": 2, "दो": 2,
            "teen": 3, "three": 3, "तीन": 3,
            "char": 4, "chaar": 4, "चार": 4,
            "paanch": 5, "five": 5, "पांच": 5, "पाँच": 5,
            "chhe": 6, "छह": 6, "छे": 6,
            "saat": 7, "सात": 7,
            "aath": 8, "आठ": 8,
            "nau": 9, "नौ": 9,
            "das": 10, "दस": 10,
            "gyarah": 11, "ग्यारह": 11,
            "baarah": 12, "बारह": 12,
            "13": 13, "14": 14, "15": 15,
            "bis": 20, "बीस": 20,
            "tis": 30, "तीस": 30,
            "chalis": 40, "चालीस": 40,
            "pachas": 50, "पचास": 50,
            "sau": 100, "सौ": 100,
        }
        quantity_str = quantity_str.strip().lower()
        if quantity_str.isdigit():
            return int(quantity_str)
        return quantity_map.get(quantity_str, 0)

    @staticmethod
    def _parse_quantity(quantity_str: str) -> tuple[int, str]:
        """Parse a quantity string into an integer quantity and a unit string."""
        if quantity_str is None:
            return 0, ""

        if isinstance(quantity_str, (int, float)):
            return int(quantity_str), ""

        s = str(quantity_str).strip().lower()
        if not s:
            return 0, ""

        # Match integers with optional unit like '2', '2kg', '2 kg', '2 kg.'
        m = re.match(r"^(\d+)(?:\s*([a-zA-Z%]+))?\.?$", s)
        if m:
            return int(m.group(1)), (m.group(2) or "")

        # Match decimals like '2.5 kg' -> convert to int
        m2 = re.match(r"^(\d+(?:\.\d+))(?:\s*([a-zA-Z%]+))?\.?$", s)
        if m2:
            return int(float(m2.group(1))), (m2.group(2) or "")

        # Word-number mapping
        qty = GeminiService._normalize_quantity(s)
        if qty > 0:
            return qty, ""

        # Fallback: find first number and treat remainder as unit
        m3 = re.search(r"(\d+)", s)
        if m3:
            num = int(m3.group(1))
            unit = s[m3.end():].strip()
            return num, unit

        return 0, ""

    @staticmethod
    def _parse_order_fallback(transcript_text: str) -> dict:
        """Fallback parser for transcripts when Gemini is unavailable."""
        transcript = GeminiService._clean_transcript(transcript_text).strip()
        if not transcript:
            return {
                "customer_name": "Unknown",
                "customer_phone": "",
                "items": [],
                "delivery_address": "",
                "delivery_time": "",
            }

        # Phone number detection
        phone_match = re.search(r"(\+?91[ \d\-]{10,}|\b\d{10}\b)", transcript)
        customer_phone = phone_match.group(1).strip() if phone_match else ""

        # Customer name heuristics
        name_match = re.search(
            r"(?:this is|main|mera naam hai|my name is|hi,? i'm|hello,? i'm|namaste,? i'm|namaste)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)",
            transcript,
            re.I,
        )
        if not name_match:
            name_match = re.search(r"(?:mera naam|naam)\s+([A-Za-z][A-Za-z ]+?)\s*(?:hai|hai\.|$)", transcript, re.I)
        if not name_match:
            name_match = re.search(
                r"^(?:(?:kal|aaj|today|tomorrow|कल|आज)\s+)?"
                r"([\w\u0900-\u097F][\w\u0900-\u097F .&'-]{1,60}?)\s+(?:ko|को)(?=\s|$)",
                transcript,
                re.I,
            )
        customer_name = name_match.group(1).strip() if name_match else "Unknown"

        # Delivery address heuristics
        address_match = re.search(
            r"(?:deliver(?:y)? to|send it to|send to|address is|ship to|pahunchao|pahunchana hai|address hai)\s+([^\.\n,]+)",
            transcript,
            re.I,
        )
        delivery_address = address_match.group(1).strip() if address_match else ""

        # Delivery time heuristics. Only capture known time phrases; never put
        # the remaining order sentence into this field.
        if re.search(r"\b(asap|immediately|right away|urgent|now|jaldi|turant|abhi)\b", transcript, re.I):
            delivery_time = "ASAP"
        else:
            time_parts = []
            for pattern in (
                r"\b(?:kal|aaj|today|tomorrow|कल|आज)\b",
                r"\b(?:subah|shaam|savera|morning|evening|raat|सुबह|शाम|रात)\b",
                r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm|baje)\b",
            ):
                time_match = re.search(pattern, transcript, re.I)
                if time_match:
                    time_parts.append(time_match.group(0))
            delivery_time = " ".join(time_parts)

        # Item heuristics with Hindi/Hinglish quantity words. Stop item names
        # at connectors or common order commands so multiple lines are kept.
        quantity_tokens = (
            r"(?:\d+(?:\.\d+)?|ek|one|do|two|teen|three|char|chaar|paanch|"
            r"five|chhe|saat|aath|nau|das|bis|tis|chalis|pachas|sau|"
            r"एक|दो|तीन|चार|पांच|पाँच|छह|छे|सात|आठ|नौ|दस|ग्यारह|बारह|बीस|तीस|चालीस|पचास|सौ)"
        )
        unit_tokens = (
            r"(?:kg|kgs|kilo|kilogram|g|gm|gram|packet|packets|pack|peti|"
            r"carton|cartons|box|boxes|litre|litres|liter|liters|l|piece|"
            r"pieces|pcs|bag|bags|tin|tins|bottle|bottles|bora|केजी|किलो|पैकेट|पेटी|बोरा)"
        )

        item_source = re.sub(
            r"^(?:(?:kal|aaj|today|tomorrow|कल|आज)\s+)?"
            r"[\w\u0900-\u097F][\w\u0900-\u097F .&'-]{1,60}?\s+(?:ko|को)(?=\s|$)",
            " ",
            transcript,
            flags=re.I,
        )
        item_source = re.sub(
            r"\b(?:kal|aaj|today|tomorrow|subah|shaam|savera|morning|evening|raat|"
            r"कल|आज|सुबह|शाम|रात)\b|\b\d{1,2}(?::\d{2})?\s*(?:am|pm|baje)\b",
            " ",
            item_source,
            flags=re.I,
        )
        item_matches = re.findall(
            rf"(?<![\w\u0900-\u097F])({quantity_tokens})\s*(?:({unit_tokens})\s+)?"
            rf"([\w\u0900-\u097F₹%+&()./'-]+(?:\s+[\w\u0900-\u097F₹%+&()./'-]+)*?)"
            rf"(?=\s+(?:and|aur|और|bhej|bhejo|bhejna|bhejdo|bhej dena|भेज|भेजो|भेजना|भेज देना|"
            rf"send|deliver|delivery|de do|dijiye|chahiye|please)(?![\w\u0900-\u097F])|[.,]|$)",
            item_source,
            re.I,
        )
        foods = []
        for quantity, unit_token, item_name in item_matches:
            name = item_name.strip(' ,.')
            qty = GeminiService._normalize_quantity(quantity)
            if qty == 0:
                # If word parsing failed, try parse_quantity (for digits)
                qty, _ = GeminiService._parse_quantity(quantity)
            
            unit = unit_token.strip()
            if name and qty > 0:
                foods.append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit,
                    "price": None,
                })

        return {
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "items": foods,
            "delivery_address": delivery_address,
            "delivery_time": delivery_time,
        }

    @staticmethod
    async def extract_order_details(transcript_text: str) -> dict:
        """Extract structured order details from transcript."""
        transcript = transcript_text.strip()
        if not transcript:
            raise ValueError("Transcript is empty.")

        if (
            not settings.GEMINI_API_KEY
            or settings.GEMINI_API_KEY == "your-gemini-api-key-here"
        ):
            return GeminiService._parse_order_fallback(transcript)

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # Create a detailed system prompt defining the output schema
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
            response = None
            models = ("gemini-2.5-flash-lite", "gemini-2.5-flash")

            for model_name in models:
                for attempt in range(3):
                    try:
                        response = await asyncio.to_thread(
                            client.models.generate_content,
                            model=model_name,
                            contents=[prompt],
                        )
                        break
                    except errors.ServerError as error:
                        if error.code != 503 or attempt == 2:
                            logger.warning(
                                "Gemini extraction model %s unavailable: %s",
                                model_name,
                                error,
                            )
                            break
                        await asyncio.sleep(2 ** attempt)
                if response:
                    break

            if not response or not getattr(response, "text", None):
                logger.warning("Gemini extraction failed or returned empty response, using fallback parser.")
                return GeminiService._parse_order_fallback(transcript)

            result_text = response.text.strip()
            parsed = None

            try:
                parsed = json.loads(result_text)
            except json.JSONDecodeError:
                # Try to extract JSON-like substring if model emits extra text.
                json_match = re.search(r"\{.*\}", result_text, re.S)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        parsed = None

            if not parsed or not isinstance(parsed, dict):
                logger.warning("Could not parse Gemini extraction output, using fallback parser.")
                return GeminiService._parse_order_fallback(transcript)
        except Exception as error:
            err_msg = str(error).upper()
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "QUOTA" in err_msg:
                logger.error(f"Gemini extraction hit quota limit: {error}")
                raise RuntimeError("Gemini API Quota Exhausted. Please try again later.") from error
            else:
                logger.exception("Gemini extraction failed.")
                raise RuntimeError(f"Gemini extraction failed: {error}") from error

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

                # --- price (dev: robust None / invalid-value handling,
                #     but default to 0.0 so the rupee-unit loop below is safe) ---
                raw_price = item.get("price")
                try:
                    price = float(raw_price) if raw_price not in (None, "", "null", "None") else 0.0
                except (ValueError, TypeError):
                    price = 0.0

                # Pass customer_phone as customer_id for ChainMap resolution
                cust_phone = parsed.get("customer_phone", "").strip()
                res = business_memory.resolve_product_detailed(item.get("name", "").strip(), customer_id=cust_phone)
                normalized_items.append({
                    "name": res["name"],
                    "quantity": qty,
                    "unit": unit,
                    "price": price,
                    "matched": res["matched"],
                    "possible_matches": res["possible_matches"]
                })

        for item in normalized_items:
            unit_lower = item["unit"].lower().strip()

            if (
                "rupee" in unit_lower
                or "rs" in unit_lower
                or "inr" in unit_lower):
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
                # Keep original raw values in the response for audit/debugging
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
                # Zip safely handles if LLM returns fewer items
                for fixed_item, orig_unresolved in zip(fixed_data["unresolved_items"], unresolved_items):
                    idx = orig_unresolved["index"]
                    
                    if fixed_item.get("raw_quantity") is not None:
                        # LLM fixed the quantity
                        normalized_items[idx]["quantity"] = fixed_item["raw_quantity"]
                        validation_warnings.append(f"AI Assist used to parse quantity for '{orig_unresolved['raw_name']}'.")
                        
                    if fixed_item.get("raw_name") and fixed_item.get("raw_name").lower() != orig_unresolved["raw_name"].lower():
                        # LLM fixed spelling, run business memory again!
                        res = business_memory.resolve_product_detailed(fixed_item["raw_name"], customer_id=cust_phone)
                        normalized_items[idx]["name"] = res["name"]
                        normalized_items[idx]["matched"] = res["matched"]
                        normalized_items[idx]["possible_matches"] = res["possible_matches"]
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
        final_data.update(risk_data)
        
        validation_data = validate_action_card(final_data, transcript)
        
        # Merge AI Fallback warnings into the main warnings list
        if "warnings" not in validation_data:
            validation_data["warnings"] = []
        validation_data["warnings"].extend(final_data.pop("validation_warnings", []))
            
        final_data.update(validation_data)
        
        return final_data
