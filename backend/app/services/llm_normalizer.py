import json
import logging
import asyncio
import re
from google import genai
from google.genai import types
from google.genai import errors
from app.config.settings import settings

logger = logging.getLogger(__name__)

class LLMNormalizer:
    @staticmethod
    async def fix_messy_fields(payload: dict) -> dict:
        """
        Layer 2 Assist Engine: 
        Takes a minimal payload of unresolved Hinglish fields and normalizes them using an LLM.
        """
        if not payload or not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your-gemini-api-key-here":
            return payload

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = (
            "You are an AI Fallback Normalizer for an Indian grocery store.\n"
            "Your ONLY job is to fix messy or misspelled Hinglish data into clean standard data.\n\n"
            "Rules:\n"
            "1. QUANTITY: If the user spoke a fraction (e.g. 'sare saath', 'paune 5', 'sawa kilo', 'dhai', 'sadhe 4'), convert it strictly to an English decimal number (e.g. 7.5, 4.75, 1.25, 2.5, 4.5). Return null if you are completely unsure.\n"
            "2. TIME: Convert messy delivery times (e.g. 'kal sawa chhe baje', 'sare aath') to 24-hour HH:MM format or specific ISO. Return null if unsure.\n"
            "3. PRODUCT SPELLING: Fix obvious spelling typos in product names (e.g. 'ptatto' -> 'potato', 'shraf exel' -> 'surf excel'). CRITICAL RULE: DO NOT infer a specific brand/variant unless it's an obvious spelling mistake. For example, if input is 'surf', output 'surf', DO NOT change it to 'Surf Excel'. If input is 'doodh', output 'doodh'. Keep generic names generic.\n"
            "4. Return STRICT JSON. You MUST use the EXACT same keys as the input payload.\n"
            "   - For unresolved_items, return an array of objects. Each object MUST have the keys 'raw_name', 'raw_quantity', and 'raw_unit' matching the input.\n"
            "   - DO NOT rename keys to 'cleaned_name' or 'cleaned_quantity'. Keep the keys identical to the input payload.\n\n"
            "Input Payload:\n"
            f"{json.dumps(payload, indent=2)}\n\n"
            "Output only JSON."
        )

        try:
            response = None
            models = ("gemini-2.5-flash-lite", "gemini-2.5-flash")

            for model_name in models:
                for attempt in range(2):
                    try:
                        response = await asyncio.to_thread(
                            client.models.generate_content,
                            model=model_name,
                            contents=[prompt],
                        )
                        break
                    except errors.ServerError as error:
                        if error.code != 503 or attempt == 1:
                            logger.warning(f"LLM Normalizer model {model_name} unavailable: {error}")
                            break
                        await asyncio.sleep(1)
                if response:
                    break

            if not response or not getattr(response, "text", None):
                return payload

            result_text = response.text.strip()
            
            # Clean Markdown formatting if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

            json_match = re.search(r"\{.*\}", result_text, re.S)
            if json_match:
                result_text = json_match.group(0)

            fixed_data = json.loads(result_text.strip())
            
            # Explicitly log raw -> normalized for audit
            if "unresolved_time" in fixed_data and fixed_data["unresolved_time"]:
                logger.info(f"LLM Normalizer [Time]: '{payload.get('unresolved_time')}' -> '{fixed_data['unresolved_time']}'")
                
            if "unresolved_items" in fixed_data and isinstance(fixed_data["unresolved_items"], list):
                for fixed_item, orig_unresolved in zip(fixed_data["unresolved_items"], payload.get("unresolved_items", [])):
                    if fixed_item.get("raw_quantity"):
                        logger.info(f"LLM Normalizer [Quantity]: '{orig_unresolved.get('raw_quantity')}' -> '{fixed_item['raw_quantity']}'")
                    if fixed_item.get("raw_name") and fixed_item["raw_name"].lower() != orig_unresolved.get("raw_name", "").lower():
                        logger.info(f"LLM Normalizer [Product]: '{orig_unresolved.get('raw_name')}' -> '{fixed_item['raw_name']}'")

            return fixed_data

        except Exception as e:
            logger.warning(f"LLM Normalizer failed: {e}")
            return payload
