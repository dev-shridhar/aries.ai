import logging
import time
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class STTAdapter:
    """Adapter for converting speech audio to text using Deepgram.

    This class provides the 'Sensory Input' layer for the Aries agent,
    allowing it to understand spoken commands.

    Attributes:
        api_key (str): The Deepgram API key for authentication.
    """

    def __init__(self, api_key: str):
        """Initializes the STTAdapter with the provided API key.

        Args:
            api_key (str): The Deepgram API key.
        """
        self.api_key = api_key

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribes raw audio bytes into a text string via Deepgram API.

        Args:
            audio_bytes (bytes): The raw audio data captured from the microphone.

        Returns:
            str: The transcribed text. Returns an empty string on failure.
        """
        if not audio_bytes or len(audio_bytes) < 1500:
            if audio_bytes:
                logger.info(f"DEEPGRAM_STT: Skipping small audio buffer ({len(audio_bytes)} bytes)")
            return ""

        try:
            logger.info(f"DEEPGRAM_STT: Transcribing {len(audio_bytes)} bytes...")
            
            # Detect mimetype
            mimetype = "audio/webm"
            if audio_bytes[:4] == b"RIFF": mimetype = "audio/wav"
            elif audio_bytes[:4] == b"fLaC": mimetype = "audio/flac"

            # Use shared client for connection pooling
            from app.infrastructure.shared_client import shared_http_client
            client = await shared_http_client.get_client()
            
            # Use simplified params for stability
            params = {
                "model": "nova-2",
                "smart_format": "true",
            }
            
            stt_start = time.time()
            response = await client.post(
                "https://api.deepgram.com/v1/listen",
                params=params,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": mimetype,
                },
                content=audio_bytes,
                timeout=15.0,
            )
            stt_duration = time.time() - stt_start
            logger.info(f"DEEPGRAM_STT: API request took {stt_duration:.2f}s")
            
            response.raise_for_status()
            data = response.json()

            transcript = ""
            if data.get("results"):
                channels = data["results"].get("channels", [])
                if channels:
                    alternatives = channels[0].get("alternatives", [])
                    if alternatives:
                        transcript = alternatives[0].get("transcript", "")

            logger.info(f"DEEPGRAM_STT: Transcript: '{transcript}'")
            return transcript

        except httpx.HTTPStatusError as e:
            logger.error(f"DEEPGRAM_STT_HTTP_ERROR: {e.response.status_code} - {e.response.text}")
            return ""
        except Exception as e:
            logger.error(f"DEEPGRAM_STT_ERROR: {e}")
            return ""


# Import the Groq adapter
from app.services.aries.pipeline.groq_stt import groq_stt_adapter


def get_stt_adapter():
    """Get the appropriate STT adapter based on configuration.

    Returns:
        The STT adapter based on settings.STT_PROVIDER
    """
    if settings.STT_PROVIDER == "groq":
        logger.info("STT: Using Groq Whisper for speech-to-text")
        return groq_stt_adapter
    else:
        logger.info("STT: Using Deepgram for speech-to-text")
        return STTAdapter(settings.DEEPGRAM_API_KEY)


# Global singleton instance - uses config to determine which adapter to use
stt_adapter = get_stt_adapter()
