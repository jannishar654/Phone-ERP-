import asyncio
import logging
import os
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

Preserve Hindi, Hinglish, English, brand names, quantities, pack sizes,
and units. Do not translate, summarize, correct, or invent information.
Write [unclear] when a word cannot be understood.
Return only the transcript.
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
    async def extract_order_details(transcript_text: str) -> dict:
        """Extract structured order details from transcript."""

        return {
            "customer_name": "Extracted Customer",
            "customer_phone": "Extracted Phone",
            "items": [
                {
                    "name": "Extracted Item",
                    "quantity": 1,
                    "price": 0.0,
                }
            ],
            "delivery_address": "Extracted Address",
            "delivery_time": "Extracted Delivery Time",
        }
