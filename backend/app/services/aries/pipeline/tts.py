import logging
import time
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class TTSAdapter:
    """Adapter for converting text characters into spoken audio using Deepgram Aura.

    This class provides the 'Motor Output' layer for the Aries agent, allowing
    it to communicate with the user through spoken words. It uses the Aura model
    leveraging Asteria (Female/US) for a natural, expressive voice.

    Attributes:
        api_key (str): The Deepgram API key for authentication.
        base_url (str): The configured Deepgram Speak endpoint with model parameters.
    """

    def __init__(self):
        """Initializes the DeepgramTTSAdapter with configured provider settings."""
        self.api_key = settings.DEEPGRAM_API_KEY
        self.base_url = (
            "https://api.deepgram.com/v1/speak"
            "?model=aura-asteria-en"
            "&encoding=linear16"
            "&container=wav"
        )

    async def speak(self, text: str) -> bytes:
        """Converts text into high-quality audio bytes.

        Args:
            text (str): The text message to be converted to speech.

        Returns:
            bytes: Raw WAV audio data in linear16 encoding.

        Raises:
            httpx.HTTPStatusError: If the Deepgram API returns a non-200 response.
        """
        import time
        from app.infrastructure.shared_client import shared_http_client
        client = await shared_http_client.get_client()
        
        tts_start = time.time()
        resp = await client.post(
            self.base_url,
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"text": text},
            timeout=10.0,
        )
        tts_duration = time.time() - tts_start
        logger.info(f"DEEPGRAM_TTS: API request took {tts_duration:.2f}s")
        
        resp.raise_for_status()
        return resp.content


# Import the Groq adapter
from app.services.aries.pipeline.groq_tts import groq_tts_adapter


def get_tts_adapter():
    """Get the appropriate TTS adapter based on configuration.

    Returns:
        The TTS adapter based on settings.TTS_PROVIDER
    """
    if settings.TTS_PROVIDER == "groq":
        logger.info("TTS: Using Groq Orpheus for text-to-speech")
        return groq_tts_adapter
    else:
        logger.info("TTS: Using Deepgram Aura for text-to-speech")
        return TTSAdapter()


# Global singleton instance - uses config to determine which adapter to use
tts_adapter = get_tts_adapter()
