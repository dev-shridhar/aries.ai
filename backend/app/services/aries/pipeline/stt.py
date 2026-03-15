import logging

from deepgram import AsyncDeepgramClient
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepgramSTTAdapter:
    """Adapter for converting speech audio to text using Deepgram.

    This class provides the 'Sensory Input' layer for the Aries agent,
    allowing it to understand spoken commands. It utilizes the high-performance
    Deepgram Nova-2 model for near-instant transcription.

    Attributes:
        api_key (str): The Deepgram API key for authentication.
        client (AsyncDeepgramClient): The asynchronous Deepgram client instance.
    """

    def __init__(self, api_key: str):
        """Initializes the DeepgramSTTAdapter with the provided API key.

        Args:
            api_key (str): The Deepgram API key.
        """
        self.api_key = api_key

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribes raw audio bytes into a text string.

        This method sends the audio data to Deepgram's Nova-2 model with
        smart formatting and English (US) language detection.

        Args:
            audio_bytes (bytes): The raw audio data captured from the microphone.

        Returns:
            str: The transcribed text. Returns an empty string on failure or
                empty input.
        """
        if not audio_bytes:
            return ""

        try:
            logger.info(
                f"DEEPGRAM_STT: Transcribing {len(audio_bytes)} bytes of audio data..."
            )

            # Use direct HTTP call to Deepgram
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    params={
                        "model": "nova-2",
                        "smart_format": "true",
                        "language": "en-US",
                    },
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": "audio/wav",
                    },
                    content=audio_bytes,
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

            # Extract the transcript from the response
            transcript = ""
            if data.get("results"):
                channels = data["results"].get("channels", [])
                if channels:
                    alternatives = channels[0].get("alternatives", [])
                    if alternatives:
                        transcript = alternatives[0].get("transcript", "")

            logger.info(
                f"DEEPGRAM_STT: Successfully extracted transcript: '{transcript}'"
            )
            return transcript

        except Exception as e:
            logger.error(f"DEEPGRAM_STT_ERROR: Deepgram transcription failed: {e}")
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
        return DeepgramSTTAdapter(settings.DEEPGRAM_API_KEY)


# Global singleton instance - uses config to determine which adapter to use
stt_adapter = get_stt_adapter()
