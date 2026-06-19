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

def aggregate_items_deterministically(normalized_items: list[dict]) -> list[dict]:
    """Pure helper to safely aggregate items by canonical name and unit."""
    aggregated_items = {}
    for item in normalized_items:
        # We already handled 'rupee'/'rs' normalizations in layer 1
        # Extract fields safely
        name = item.get("name", "Unknown Item")
        unit_lower = str(item.get("unit") or "").lower().strip()
        
        # Key uses canonical name (which inherently includes variant/pack_size) and unit
        key = (name, unit_lower)
        
        if key not in aggregated_items:
            aggregated_items[key] = item.copy()
        else:
            # Safely handle decimal quantities and missing quantities
            existing_qty = aggregated_items[key].get("quantity")
            new_qty = item.get("quantity")
            
            if existing_qty is not None and new_qty is not None:
                try:
                    total_qty = float(existing_qty) + float(new_qty)
                    # Convert to int if no fractional part to keep UI clean
                    aggregated_items[key]["quantity"] = int(total_qty) if total_qty.is_integer() else total_qty
                except (ValueError, TypeError):
                    logger.warning(f"Failed to add quantities '{existing_qty}' and '{new_qty}' for {name}")
            elif existing_qty is None and new_qty is not None:
                aggregated_items[key]["quantity"] = new_qty
            
            # Use max price if multiple prices are provided
            existing_price = aggregated_items[key].get("price", 0.0)
            new_price = item.get("price", 0.0)
            try:
                aggregated_items[key]["price"] = max(float(existing_price), float(new_price))
            except (ValueError, TypeError):
                pass
                
    final_aggregated = list(aggregated_items.values())
    if not final_aggregated:
        return [{"name": "Unknown Item", "quantity": 1, "unit": "", "price": 0.0}]
    return final_aggregated

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
    def _parse_quantity(quantity_str: str) -> tuple[int | float | None, str]:
        """Parse a quantity string into an integer or float quantity and a unit string."""
        if quantity_str is None:
            return None, ""

        if isinstance(quantity_str, (int, float)):
            return quantity_str, ""

        s = str(quantity_str).strip().lower()
        if not s or s == "none" or s == "null":
            return None, ""

        # Match integers with optional unit like '2', '2kg', '2 kg', '2 kg.'
        m = re.match(r"^(\d+)(?:\s*([a-zA-Z%]+))?\.?$", s)
        if m:
            return int(m.group(1)), (m.group(2) or "")

        # Match decimals like '2.5 kg' -> preserve float
        m2 = re.match(r"^(\d+(?:\.\d+))(?:\s*([a-zA-Z%]+))?\.?$", s)
        if m2:
            return float(m2.group(1)), (m2.group(2) or "")

        # Word-number mapping
        qty = GeminiService._normalize_quantity(s)
        if qty > 0:
            return qty, ""

        # Fallback: find first decimal or integer and treat remainder as unit
        m3 = re.search(r"(\d+(?:\.\d+)?)", s)
        if m3:
            num_str = m3.group(1)
            num = float(num_str) if '.' in num_str else int(num_str)
            unit = s[m3.end():].strip()
            return num, unit

        return None, ""

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
                parsed_qty, _ = GeminiService._parse_quantity(quantity)
                qty = parsed_qty if parsed_qty is not None else 0
            
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
        
        # --- Normalization Layer for Devanagari (One-Call Unified) ---
        transcript_original = transcript
        has_devanagari = bool(re.search(r'[\u0900-\u097F]', transcript))
        
        enable_transliteration = getattr(settings, "ENABLE_LLM_TRANSLITERATION", False)
        
        normalization_instruction = ""
        output_schema_additions = ""
        if has_devanagari and enable_transliteration:
            normalization_instruction = (
                "2. NORMALIZE TRANSCRIPT: The transcript contains Devanagari. You MUST transliterate it into Romanized Hinglish and output it as `transcript_normalized` in the root JSON. Preserve all English brand names natively. Convert Hindi number words to Arabic digits ('पाँच' -> '5'). Transliterate fractional Hindi times phonetically ('साढ़े पाँच' -> 'saade paanch'). Record the exact phonetic transformation mappings (e.g., 'साढ़े पाँच' -> 'saade paanch', 'पाँच' -> '5') in `metadata.model_normalizer_notes`.\n"
            )
            output_schema_additions = (
                '  "transcript_normalized": "string (Romanized Hinglish transliteration)",\n'
                '  "metadata": {"model_normalizer_notes": ["string"], "cancelled_items": [{"name": "string", "quantity": "string", "unit": "string"}]},\n'
            )
        else:
            normalization_instruction = "2. NORMALIZE TRANSCRIPT: Output the exact original transcript as `transcript_normalized` in the root JSON.\n"
            output_schema_additions = '  "transcript_normalized": "string",\n  "metadata": {"cancelled_items": [{"name": "string", "quantity": "string", "unit": "string"}]},\n'

        prompt = (
            "You are an expert grocery order extraction AI for PhoneERP, an Indian grocery/wholesale/kirana business.\n"
            "Your task is to extract structured entities from a customer transcript.\n"
            "Clients may speak Hindi (Devanagari), English, or Hinglish (mixed).\n\n"
            "## CORE RULES\n"
            "1. ALL EXTRACTED VALUES IN CARDS MUST BE IN ENGLISH LETTERS (ROMANIZED HINGLISH). DO NOT OUTPUT ANY DEVANAGARI/HINDI SCRIPT inside the `cards` array. Do not invent missing fields.\n"
            f"{normalization_instruction}"
            "3. ISOLATE CORE PRODUCT NAMES: Strictly separate the core product name from its quantity, unit, or packaging type. The `name` field must ONLY contain the core product. NEVER include numbers, units (kilo, liter), or packaging words (packet, thaili, dabba) in the `name` field. Product names often include local aliases, shorthand, and pack variants.\n"
            "   - Example: 'ek badi thaili doodh ki' -> name: 'bada doodh', quantity: '1', unit: 'thaili'\n"
            "4. SYNTHESIZE FULL ADDRESSES: For `customer_name` and `delivery_address`, NEVER output Devanagari. Transliterate EXACTLY as spoken phonetically. DO NOT hallucinate, guess, or 'correct' location names.\n"
            "5. CLEAN ITEM NAMES: Remove all conversational action verbs from item names (e.g., 'bhijwa dena', 'pack kar dena').\n"
            "6. GROCERY STORE CONTEXT: Assume all items are standard grocery or household products. Do not hallucinate non-grocery words.\n"
            "7. DO NOT AGGREGATE DUPLICATES: If the same item is mentioned multiple times in the transcript, extract each mention as a SEPARATE item in the list. Do NOT do math. We will aggregate them later.\n"
            "8. NEVER MERGE UNRELATED ITEMS: Do not accidentally glue two completely different products into one name. Extract 'surf excel' and 'chawal' as TWO separate items. NEVER extract 'surf excel chawal'.\n"
            "9. PRESERVE RAW DELIVERY TIME: Detect time phrases (e.g., 'kal 5:30 baje', 'कल साढ़े पाँच बजे') and extract EXACTLY as it appears in the NORMALIZED transcript into `delivery_time_raw`. Do not put delivery-time words inside `delivery_address`.\n"
            "10. EXACT RAW QUANTITY & UNIT: For the 'quantity' field in items, extract the exact raw numerical quantity spoken. Do not do math or silently default to 1. If quantity is missing, use null. Preserve spoken units (e.g., 'packet', 'kilo') exactly as spoken in the `unit` field.\n"
            "11. EXTRACT CUSTOMER NAME: If transcript explicitly says 'unka naam X hai' or 'naam X rahega', use X as `customer_name`. If a store/location is mentioned instead of a person, use the store name as the customer_name (e.g. 'Guptastore'). Do not leave customer_name as Unknown if a name or store name is clearly spoken. Do not invent names.\n"
            "12. DETECT PAYMENT METHOD/UDHAAR: If the user says 'udhaar', 'paisa udhaar rahega', 'baad mein denge', 'credit', or 'khata mein likh do', set `payment_method` to 'Credit/Udhaar' and add a note in `extraction_notes`.\n"
            "13. FLAG UNKNOWN/AMBIGUOUS FIELDS: Add warnings to extraction_notes if product/quantity is ambiguous.\n"
            "14. IN-FLIGHT CANCELLATIONS: If an item is added but later cancelled in the same transcript (e.g. 'ek tight surf add karo... nahi surf cancel kar dena'), DO NOT include it in `items`. Place it in `metadata.cancelled_items` instead.\n\n"
            "## OUTPUT FORMAT\n"
            "Return ONLY a JSON object containing `transcript_normalized` and a `cards` array. No markdown, no explanation.\n"
            "{\n"
            f"{output_schema_additions}"
            '  "cards": [\n'
            "    {\n"
            '      "type": "ORDER" | "CANCEL" | "COMPLAINT" | "RETURN" | "QUERY" | "PAYMENT_REMINDER",\n'
            '      "customer_name": "string (Extract exact name or store. Use UNKNOWN only if completely unclear)",\n'
            '      "customer_phone": "string",\n'
            '      "items": [{"name": "string (never prefix with missing)", "quantity": "STRING or null", "unit": "string or null", "price": number}],\n'
            '      "delivery_address": "string",\n'
            '      "delivery_time_raw": "string",\n'
            '      "payment_method": "string (e.g. Cash, Online, Credit/Udhaar)",\n'
            '      "confidence": number (0.0 to 1.0. Reduce if name/qty/product is unclear),\n'
            '      "extraction_notes": "string (notes on ambiguity, missing fields, risky instructions, multiple orders, or unknown products)"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "## EXAMPLES\n"
            "- Local alias: 'lal Surf dena' -> name: 'lal Surf'\n"
            "- Pack variant: 'dus wala Parle' -> name: 'dus wala Parle'\n"
            "- Credit: 'udhaar mein likh dena' -> payment_method: 'Credit/Udhaar', extraction_notes: 'User requested udhaar/credit'\n"
            "- Time & Name: 'kal aisa karna 5:30 baje Guptastore... unka naam Shayam hai' -> customer_name: 'Shayam', delivery_time_raw: 'kal 5:30 baje', delivery_address: 'Guptastore'\n"
            "- Cancellation: 'kal wala chips cancel kar do' -> type: 'CANCEL', extraction_notes: 'Cancelling previous chips order'\n"
            "- Substitution: 'Parle nahi hai toh Britannia bhej dena' -> extraction_notes: 'Substitution requested: Britannia if Parle unavailable'\n"
            "- Incomplete order: 'chips bhej dena' -> items: [{\"name\": \"chips\", \"quantity\": null, \"unit\": null}], extraction_notes: 'Quantity not specified for chips'\n\n"
            f"Transcript:\n{transcript_original}\n"
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

        # Safely extract the first card from the cards array.
        # Ensure compatibility with multiple cards structure without breaking existing single-card endpoints.
        cards = parsed.get("cards", [])
        if not cards or not isinstance(cards, list):
            # Fallback if model didn't wrap it in a cards array
            cards = [parsed]
        
        primary_card = cards[0]
        # Flag if multiple cards were present so endpoints can log it
        if len(cards) > 1:
            primary_card["_multi_card_flag"] = True

        transcript_normalized = parsed.get("transcript_normalized")
        if not transcript_normalized or not isinstance(transcript_normalized, str):
            transcript_normalized = transcript_original
            
        normalization_metadata = parsed.get("metadata", {})
        normalization_used = transcript_normalized != transcript_original
        normalization_warnings = None

        items = primary_card.get("items") or []
        if not isinstance(items, list):
            items = []

        normalized_items = []
        for item in items:
            if isinstance(item, dict):
                # --- quantity + unit (new pipeline) ---
                raw_qty = item.get("quantity")
                raw_unit = item.get("unit", "")
                
                # If LLM passed a string containing quantity and unit, pipe it to quantity_parser
                from app.services.quantity_parser import parse_quantity
                from app.services.unit_normalizer import normalize_unit
                
                combined_raw = f"{raw_qty} {raw_unit}".strip()
                parsed_qty_data = parse_quantity(combined_raw)
                
                qty = parsed_qty_data["quantity"]
                unit_str = parsed_qty_data["unit"] or str(raw_unit)
                
                # Fallback to Nasir/dev logic
                if qty is None:
                    fallback_qty, fallback_unit = GeminiService._parse_quantity(str(raw_qty))
                    if fallback_qty is not None:
                        qty = fallback_qty
                    if fallback_unit and not parsed_qty_data["unit"]:
                        unit_str = fallback_unit
                
                unit = normalize_unit(unit_str)

                # --- price (dev: robust None / invalid-value handling,
                #     but default to 0.0 so the rupee-unit loop below is safe) ---
                raw_price = item.get("price")
                try:
                    price = float(raw_price) if raw_price not in (None, "", "null", "None") else 0.0
                except (ValueError, TypeError):
                    price = 0.0

                # Pass customer_phone as customer_id for ChainMap resolution
                cust_phone = parsed.get("customer_phone", "")
                cust_phone = cust_phone.strip() if cust_phone else ""
                
                raw_name = item.get("name")
                safe_name = raw_name.strip() if raw_name else "Unknown Item"
                
                lower_name = safe_name.lower()
                for prefix in ("none ", "missing ", "null ", "unknown "):
                    if lower_name.startswith(prefix):
                        safe_name = safe_name[len(prefix):].strip()
                        qty = None
                        break

                res = business_memory.resolve_product_detailed(safe_name, customer_id=cust_phone)
                normalized_items.append({
                    "name": res["name"],
                    "quantity": qty,
                    "unit": unit,
                    "price": price,
                    "matched": res["matched"],
                    "possible_matches": res["possible_matches"]
                })

        for item in normalized_items:
            unit_lower = str(item.get("unit") or "").lower().strip()

            if (
                "rupee" in unit_lower
                or "rs" in unit_lower
                or "inr" in unit_lower):
                item["price"] = max(item["price"], float(item["quantity"] or 0))
                item["quantity"] = 1
                item["unit"] = ""

        # --- Deterministic Cancellation Filter ---
        cancelled_items = normalization_metadata.get("cancelled_items", [])
        cancelled_names = [str(ci.get("name", "")).strip().lower() for ci in cancelled_items if ci.get("name")]
        
        has_cancellation = False
        final_items = []
        for item in normalized_items:
            item_name_lower = str(item.get("name", "")).lower()
            is_cancelled = False
            for cn in cancelled_names:
                if cn in item_name_lower or item_name_lower in cn:
                    is_cancelled = True
                    break
            
            if is_cancelled:
                has_cancellation = True
                continue
            final_items.append(item)
            
        normalized_items = final_items

        if not normalized_items:
            normalized_items = [{"name": "Unknown Item", "quantity": 1, "unit": "", "price": 0.0}]

        raw_cust_name = primary_card.get("customer_name", "")
        cust_name = raw_cust_name.strip() if raw_cust_name else ""
        
        # Apply deterministic time parsing
        raw_delivery_time = primary_card.get("delivery_time_raw", primary_card.get("delivery_time", ""))
        safe_delivery_time = raw_delivery_time.strip() if raw_delivery_time else ""

        # --- Deterministic Fallbacks for Missing Fields ---
        t_lower = transcript_normalized.lower()
        
        if not cust_name or cust_name.lower() == "unknown":
            name_match = re.search(r'(?:unka naam|naam|customer ka naam|party ka naam|नाम|उनका नाम|पार्टी का नाम)\s+(.*?)(?:\s+(?:hai|tha|aur|rahega|है|था|और|रहेगा)|$)', t_lower)
            if name_match:
                cust_name = name_match.group(1).strip().title()
                
        if not safe_delivery_time:
            # Detect clock expression independently
            clock_regex = r'\b(?:sade|saade|sawa|paune|dhai|dedh|aadha|साढ़े|साढ़े|सवा|पौने|ढाई|डेढ़|आधा|[0-9]+(?:[:.][0-9]+)?|ek|do|teen|char|paanch|chhe|saat|aath|nau|das|gyarah|barah|एक|दो|तीन|चार|पाँच|छह|सात|आठ|नौ|दस|ग्यारह|बारह)(?:\s+(?:[0-9]+|ek|do|teen|char|paanch|chhe|saat|aath|nau|das|gyarah|barah|एक|दो|तीन|चार|पाँच|छह|सात|आठ|नौ|दस|ग्यारह|बारह))?\s*(?:baje|bje|am|pm|बजे|बजे)\b'
            clocks = list(re.finditer(clock_regex, t_lower))
            
            if clocks:
                last_clock = clocks[-1]
                clock_str = last_clock.group(0)
                clock_start = last_clock.start()
                clock_end = last_clock.end()
                
                # Search within a bounded window (50 chars before) for a day token
                window_start = max(0, clock_start - 50)
                window_text = t_lower[window_start:clock_start]
                
                # In time context, safely recognize ASR variants kall/kalle
                day_matches_in_window = list(re.finditer(r'\b(kal|kall|kalle|aaj|parso|subah|dopahar|shaam|raat|कल|आज|परसों|सुबह|दोपहर|शाम|रात)\b', window_text))
                if day_matches_in_window:
                    last_day_match = day_matches_in_window[-1]
                    abs_day_start = window_start + last_day_match.start()
                    raw_delivery_time = t_lower[abs_day_start:clock_end]
                else:
                    # Clock detected but day uncertain, preserve clock
                    raw_delivery_time = clock_str
                    
                safe_delivery_time = raw_delivery_time
            else:
                # Fallback: Day only
                day_matches = list(re.finditer(r'\b(kal|aaj|parso|कल|आज|परसों)\b', t_lower))
                if day_matches:
                    raw_delivery_time = day_matches[-1].group(0)
                    safe_delivery_time = raw_delivery_time
                
        if cust_name:
            cust_name = re.sub(r'(?:\s+(?:likhna|likh\s*dena|likhdo|rakhna|karna|bhejna|dena|hai|theek\s*hai|लिखना|लिख\s*देना|लिखदो|रखना|करना|भेजना|देना|है|ठीक\s*है))+$', '', cust_name, flags=re.IGNORECASE).strip()
                
        normalized_cust = normalize_alias(cust_name, BUSINESS_ALIASES["customer_aliases"])
        time_data = parse_delivery_time(safe_delivery_time)

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

        # --- Aggregate duplicate items deterministically ---
        final_aggregated_items = aggregate_items_deterministically(normalized_items)

        logger.debug("--- GEMINI EXTRACTION DEBUG ---")
        logger.debug(f"Raw Gemini Items: {items}")
        logger.debug(f"Normalized Items: {normalized_items}")
        logger.debug(f"Final Aggregated Items: {final_aggregated_items}")
        logger.debug("-------------------------------")

        final_data = {
            "customer_name": normalized_cust,
            "customer_phone": str(primary_card.get("customer_phone") or "").strip(),
            "delivery_address": str(primary_card.get("delivery_address") or "").strip(),
            "delivery_time_raw": raw_delivery_time,
            "delivery_time_normalized": time_data["normalized"],
            "delivery_time_confidence": time_data["confidence"],
            "delivery_time_warning": time_data["warning"],
            "delivery_time": time_data["normalized"] or raw_delivery_time, # fallback for UI compatibility
            "payment_method": str(primary_card.get("payment_method") or "").strip() or None,
            "items": final_aggregated_items,
            "type": primary_card.get("type", "ORDER"),
            "confidence": primary_card.get("confidence", 0.0),
            "extraction_notes": primary_card.get("extraction_notes", ""),
            "_multi_card_flag": primary_card.get("_multi_card_flag", False),
            "validation_warnings": validation_warnings,
            "metadata": {
                "transcript_original": transcript_original,
                "transcript_normalized": transcript_normalized,
                "normalization_used": normalization_used,
                "normalization_warnings": normalization_warnings,
                "model_normalizer_notes": normalization_metadata.get("model_normalizer_notes", []),
                "cancelled_items": normalization_metadata.get("cancelled_items", []),
                "stt_provider": "sarvam", # Assuming sarvam_gemini handles this by default as requested
                "extraction_provider": "gemini",
                "pipeline": "sarvam_gemini"
            }
        }

        # Apply deterministic action card validation
        from app.services.risk_detector import detect_risks
        risk_data = detect_risks(transcript, final_aggregated_items)
        if has_cancellation and "cancellation" not in risk_data["risk_flags"]:
            risk_data["risk_flags"].append("cancellation")
        final_data.update(risk_data)
        
        validation_data = validate_action_card(final_data, transcript)
        
        # Merge AI Fallback warnings into the main warnings list
        if "warnings" not in validation_data:
            validation_data["warnings"] = []
        validation_data["warnings"].extend(final_data.pop("validation_warnings", []))
            
        final_data.update(validation_data)
        
        return final_data
