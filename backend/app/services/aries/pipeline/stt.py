import logging
import asyncio
import httpx
from typing import Any, Callable
from app.core.config import settings

logger = logging.getLogger(__name__)


class STTAdapter:
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
        self.base_url = "https://api.deepgram.com/v1/listen"

    async def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribes audio bytes using Deepgram's REST API (sync).
        Buffers audio until silence is detected or timeout.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": "audio/webm",
                    },
                    params={
                        "model": "nova-2-general",
                        "smart_format": "true",
                        "punctuate": "true",
                    },
                    content=audio_bytes,
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("results", {}).get("channels"):
                    transcript = (
                        data["results"]["channels"][0]
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
                    return transcript or ""
                return ""
        except Exception as e:
            logging.getLogger(__name__).error(f"STT Transcription Error: {e}")
            return ""

    async def transcribe_from_buffer(self, audio_chunks: list[bytes]) -> str:
        """Transcribe from accumulated audio chunks."""
        if not audio_chunks:
            return ""

        combined_audio = b"".join(audio_chunks)
        return await self.transcribe(combined_audio)


stt_adapter = STTAdapter()
