import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GroqTTSAdapter:
    """Adapter for converting text to speech using Groq Orpheus.

    This class provides the 'Motor Output' layer for the Aries agent,
    allowing it to communicate with the user through spoken words.
    It uses the Orpheus model for expressive, natural voice.

    Attributes:
        api_key (str): The Groq API key for authentication.
    """

    def __init__(self, api_key: str):
        """Initializes the GroqTTSAdapter with the provided API key.

        Args:
            api_key (str): The Groq API key.
        """
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1/audio/speech"
        self.model = "canopylabs/orpheus-v1-english"
        self.voice = "austin"  # Default voice

    async def speak(self, text: str) -> bytes:
        """Converts text into high-quality audio bytes.

        Args:
            text (str): The text message to be converted to speech.

        Returns:
            bytes: Raw WAV audio data.

        Raises:
            httpx.HTTPStatusError: If the Groq API returns a non-200 response.
        """
        try:
            logger.info(f"GROQ_TTS: Converting text to speech ({len(text)} chars)...")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    json={
                        "model": self.model,
                        "input": text,
                        "voice": self.voice,
                        "response_format": "wav",
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.content

        except Exception as e:
            logger.error(f"GROQ_TTS_ERROR: TTS generation failed: {e}")
            raise


# Global singleton instance for Groq TTS.
groq_tts_adapter = GroqTTSAdapter(settings.GROQ_API_KEY)
