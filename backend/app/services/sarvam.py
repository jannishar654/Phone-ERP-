import logging
import os
import httpx
import tempfile
import asyncio
import subprocess
from app.config.settings import settings
import glob

logger = logging.getLogger(__name__)

class SarvamService:
    @staticmethod
    async def _transcribe_chunk(client: httpx.AsyncClient, chunk_path: str, api_key: str) -> str:
        url = "https://api.sarvam.ai/speech-to-text"
        headers = {"api-subscription-key": api_key}
        data = {"model": "saaras:v3"}
        
        with open(chunk_path, "rb") as f:
            file_content = f.read()
            
        filename = os.path.basename(chunk_path)
        files = {"file": (filename, file_content)}
        
        try:
            response = await client.post(url, headers=headers, files=files, data=data, timeout=60.0)
            response.raise_for_status()
            result = response.json()
            
            transcript = result.get("transcript", "")
            if not transcript and "data" in result:
                transcript = result["data"].get("transcript", "")
                
            return transcript.strip()
        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            try:
                error_json = e.response.json()
                error_body = error_json.get("error", {}).get("message", e.response.text)
            except Exception:
                pass
            logger.error(f"Sarvam API rejected chunk {filename} ({e.response.status_code}): {error_body}")
            raise RuntimeError(f"Sarvam API Error: {error_body}") from e
        except Exception as e:
            logger.exception(f"Sarvam audio transcription failed for chunk {filename}.")
            raise RuntimeError(f"Sarvam transcription failed: {e}") from e

    # --- Configuration Constants ---
    MAX_AUDIO_DURATION_SECONDS = 120
    MAX_CHUNKS = 10
    IDEAL_CHUNK_SECONDS = 12.0
    HARD_MAX_CHUNK_SECONDS = 28.0
    MAX_PARALLEL_STT_REQUESTS = 3
    FALLBACK_OVERLAP_SECONDS = 0.5
    SILENCE_NOISE_THRESHOLD_DB = -30
    SILENCE_MIN_DURATION_SECONDS = 0.5

    @staticmethod
    async def _transcribe_chunk_with_sem(sem: asyncio.Semaphore, client: httpx.AsyncClient, chunk_path: str, api_key: str) -> str:
        async with sem:
            return await SarvamService._transcribe_chunk(client, chunk_path, api_key)

    @staticmethod
    def _get_audio_duration(file_path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode != 0:
                logger.error(f"ffprobe failed: {result.stderr}")
                return 0.0
            return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0

    @staticmethod
    def _detect_silences(clean_wav_path: str) -> list:
        # Detect silences. We look for the 'silence_end' tags in stderr.
        cmd = [
            "ffmpeg", "-i", clean_wav_path,
            "-af", f"silencedetect=noise={SarvamService.SILENCE_NOISE_THRESHOLD_DB}dB:d={SarvamService.SILENCE_MIN_DURATION_SECONDS}",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        silence_ends = []
        for line in result.stderr.splitlines():
            if "silence_end" in line:
                # e.g., [silencedetect @ 0x123456] silence_end: 12.345
                parts = line.split("silence_end:")
                if len(parts) > 1:
                    try:
                        time_str = parts[1].split("|")[0].strip()
                        silence_ends.append(float(time_str))
                    except ValueError:
                        pass
        return sorted(silence_ends)

    @staticmethod
    def _calculate_chunk_boundaries(duration: float, silence_ends: list) -> list:
        chunks = []
        current_start = 0.0
        
        while current_start < duration:
            # Find silences that fall within our allowed chunk window
            valid_silences = [s for s in silence_ends if current_start < s <= current_start + SarvamService.HARD_MAX_CHUNK_SECONDS]
            
            if valid_silences:
                # Try to find a silence that satisfies IDEAL_CHUNK_SECONDS
                ideal_silences = [s for s in valid_silences if s >= current_start + SarvamService.IDEAL_CHUNK_SECONDS]
                if ideal_silences:
                    split_point = ideal_silences[0]
                else:
                    # If none reach the ideal length, just pick the latest valid silence
                    split_point = valid_silences[-1]
                    
                chunks.append((current_start, split_point))
                current_start = split_point
            else:
                # No silence found in the HARD_MAX window. We must forcefully split.
                split_point = min(current_start + SarvamService.HARD_MAX_CHUNK_SECONDS, duration)
                chunks.append((current_start, split_point))
                
                # Apply overlap for the next chunk, but only if we haven't reached the end
                if split_point < duration:
                    current_start = max(0.0, split_point - SarvamService.FALLBACK_OVERLAP_SECONDS)
                else:
                    current_start = split_point
                    
        return chunks

    @staticmethod
    async def transcribe_audio_file(file_content: bytes, filename: str) -> str:
        """Upload audio to Sarvam AI and return its transcript using silence-based segmentation."""
        if not file_content:
            raise ValueError("Audio file is empty.")

        api_key = settings.SARVAM_API_KEY
        if not api_key:
            raise ValueError("SARVAM_API_KEY is not configured.")

        original_ext = os.path.splitext(filename)[1].lower() or ".tmp"
        
        temp_dir = tempfile.mkdtemp()
        in_path = os.path.join(temp_dir, f"input{original_ext}")
        clean_path = os.path.join(temp_dir, "clean.wav")
        
        try:
            with open(in_path, "wb") as f:
                f.write(file_content)

            # 1. Verify Audio Duration
            duration = SarvamService._get_audio_duration(in_path)
            logger.info(f"Audio duration measured: {duration} seconds.")
            
            if duration > SarvamService.MAX_AUDIO_DURATION_SECONDS:
                raise ValueError(f"Audio is too long ({duration:.1f}s). Maximum allowed is {SarvamService.MAX_AUDIO_DURATION_SECONDS}s.")

            # 2. Normalize Audio
            process = subprocess.run(
                ["ffmpeg", "-y", "-i", in_path, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-map_metadata", "-1", clean_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if process.returncode != 0:
                logger.error(f"ffmpeg normalization failed: {process.stderr.decode('utf-8', errors='ignore')}")
                raise ValueError("Audio recording is corrupted or unsupported.")

            # Re-measure duration on clean file just in case
            duration = SarvamService._get_audio_duration(clean_path)
            
            if duration <= SarvamService.HARD_MAX_CHUNK_SECONDS:
                # No chunking needed
                chunks = [(0.0, duration)]
            else:
                # 3. Detect Silences
                silence_ends = SarvamService._detect_silences(clean_path)
                logger.info(f"Detected silence boundaries: {silence_ends}")
                
                # 4. Calculate Boundaries
                chunks = SarvamService._calculate_chunk_boundaries(duration, silence_ends)

            if len(chunks) > SarvamService.MAX_CHUNKS:
                raise ValueError(f"Audio is too complex and generated too many chunks ({len(chunks)}). Maximum allowed is {SarvamService.MAX_CHUNKS}.")
                
            logger.info(f"Calculated {len(chunks)} chunks: {chunks}")

            # 5. Generate Chunk Files
            chunk_files = []
            for i, (start, end) in enumerate(chunks):
                chunk_dur = end - start
                chunk_file = os.path.join(temp_dir, f"chunk_{i:03d}.wav")
                cmd = ["ffmpeg", "-y", "-i", clean_path, "-ss", str(start), "-t", str(chunk_dur), "-c", "copy", chunk_file]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                chunk_files.append(chunk_file)

            if not chunk_files:
                raise ValueError("Failed to split audio into chunks.")
                
            # 6. Process Chunks Concurrently with Semaphore Limit
            sem = asyncio.Semaphore(SarvamService.MAX_PARALLEL_STT_REQUESTS)
            async with httpx.AsyncClient() as client:
                tasks = []
                for chunk_file in chunk_files:
                    tasks.append(SarvamService._transcribe_chunk_with_sem(sem, client, chunk_file, api_key))
                    
                # gather preserves the chronological order of the tasks!
                chunk_transcripts = await asyncio.gather(*tasks)
                
            # 7. Stitch transcript
            # TODO: If fallback overlap was used, there might be slightly duplicated words at boundaries.
            # Clean them up later if necessary via NLP fuzzy deduplication.
            full_transcript = " ".join([t for t in chunk_transcripts if t]).strip()
            
            if not full_transcript:
                logger.warning("Sarvam returned empty transcripts for all chunks.")
            
            return full_transcript
            
        finally:
            # Cleanup temp dir and all files inside
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(temp_dir)
