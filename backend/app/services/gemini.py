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

            transcript = response.text.strip() if response.text else ""

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
            "ek": 1,
            "one": 1,
            "do": 2,
            "two": 2,
            "teen": 3,
            "three": 3,
            "char": 4,
            "chaar": 4,
            "paanch": 5,
            "five": 5,
            "chhe": 6,
            "saat": 7,
            "aath": 8,
            "nau": 9,
            "das": 10,
            "gyarah": 11,
            "baarah": 12,
            "13": 13,
            "14": 14,
            "15": 15,
        }
        quantity_str = quantity_str.strip().lower()
        if quantity_str.isdigit():
            return int(quantity_str)
        return quantity_map.get(quantity_str, 0)

    @staticmethod
    def _parse_quantity(quantity_str: str) -> tuple[float, str]:
        """Parse a quantity string into a numeric quantity and a unit string."""
        if quantity_str is None:
            return 0.0, ""

        if isinstance(quantity_str, (int, float)):
            return float(quantity_str), ""

        s = str(quantity_str).strip().lower()
        if not s:
            return 0, ""

        # Match integers with optional unit like '2', '2kg', '2 kg', '2 kg.'
        m = re.match(r"^(\d+)(?:\s*([a-zA-Z%]+))?\.?$", s)
        if m:
            return int(m.group(1)), (m.group(2) or "")

        # Match decimals like '2.5 kg'.
        m2 = re.match(r"^(\d+(?:\.\d+))(?:\s*([a-zA-Z%]+))?\.?$", s)
        if m2:
            return float(m2.group(1)), (m2.group(2) or "")

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
        transcript = transcript_text.strip()
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
        customer_name = name_match.group(1).strip() if name_match else "Unknown"

        # Delivery address heuristics
        address_match = re.search(
            r"(?:deliver(?:y)? to|send it to|send to|address is|ship to|pahunchao|pahunchana hai|address hai)\s+([^\.\n,]+)",
            transcript,
            re.I,
        )
        delivery_address = address_match.group(1).strip() if address_match else ""

        # Delivery time heuristics
        if re.search(r"\b(asap|immediately|right away|urgent|now|jaldi|turant|abhi)\b", transcript, re.I):
            delivery_time = "ASAP"
        else:
            time_match = re.search(r"(?:by|for|on|at|se|tak|subah|shaam|kal|aaj|savera)\s+([^\.\n,]+)", transcript, re.I)
            delivery_time = time_match.group(1).strip() if time_match else ""

        # Item heuristics with Hindi/Hinglish quantity words
        quantity_tokens = r"(?:\d+|ek|one|do|two|teen|three|char|chaar|paanch|five|chhe|saat|aath|nau|das)"
        item_matches = re.findall(
            rf"({quantity_tokens})(?:\s*([a-zA-Z%]+))?\s+(?:of\s+)?([\w\-,\(\)\/ ]+?)(?=\s+(?:and|aur|with|ke liye|for|from|to|delivered|deliver|address|by|at|\.|,|$))",
            transcript,
            re.I,
        )
        foods = []
        for quantity, unit_token, item_name in item_matches:
            name = item_name.strip(' ,.')
            qty_str = quantity + (f" {unit_token}" if unit_token else "")
            qty, unit = GeminiService._parse_quantity(qty_str)
            if name and qty > 0:
                foods.append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit,
                    "price": None,
                })

        if not foods:
            single_item_match = re.search(
                r"(?:need|order|want|send me|give me|mujhe|chahiye|lijiye|de dijiye|de do)\s+([\w\-,\(\)\/ ]+?)(?:\s+to|\s+for|\s+at|\s+by|\s+ke liye|\s+k liye|\.|,|$)",
                transcript,
                re.I,
            )
            if single_item_match:
                item_text = single_item_match.group(1).strip(' ,.')
                foods.append({"name": item_text, "quantity": 1, "unit": "", "price": None})

        if not foods:
            foods = [{"name": "Unknown Item", "quantity": 1, "unit": "", "price": None}]

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

        prompt = (
            "Extract the order details from the customer transcript and return only valid JSON with the following keys:\n"
            "customer_name, customer_phone, delivery_address, delivery_time, items.\n"
            "items must be an array of objects with name, quantity, unit, price.\n"
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
                logger.warning(f"Gemini extraction hit quota limit ({error}). Falling back to local parser.")
            else:
                logger.exception("Gemini extraction failed, using fallback parser.")
            return GeminiService._parse_order_fallback(transcript)

        items = parsed.get("items") or []
        if not isinstance(items, list):
            items = []

        normalized_items = []
        for item in items:
            if isinstance(item, dict):
                # --- quantity + unit (nasir: richer parsing) ---
                raw_qty = item.get("quantity", 0)
                unit_hint = (item.get("unit") or "").strip()
                if isinstance(raw_qty, (int, float)):
                    qty = float(raw_qty)
                    unit = unit_hint
                else:
                    qty, parsed_unit = GeminiService._parse_quantity(str(raw_qty))
                    unit = parsed_unit or unit_hint

                # --- price (dev: robust None / invalid-value handling,
                #     but default to 0.0 so the rupee-unit loop below is safe) ---
                raw_price = item.get("price")
                try:
                    price = float(raw_price) if raw_price not in (None, "", "null", "None") else 0.0
                except (ValueError, TypeError):
                    price = 0.0

                normalized_items.append({
                    "name": item.get("name", "").strip(),
                    "quantity": qty,
                    "unit": unit,
                    "price": price,
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

        return {
            "customer_name": parsed.get("customer_name", "").strip(),
            "customer_phone": parsed.get("customer_phone", "").strip(),
            "delivery_address": parsed.get("delivery_address", "").strip(),
            "delivery_time": parsed.get("delivery_time", "").strip(),
            "items": normalized_items,
        }
