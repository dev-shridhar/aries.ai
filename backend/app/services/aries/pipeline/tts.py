import httpx
from app.core.config import settings


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
        """Initializes the TTSAdapter with configured provider settings."""
        self.api_key = settings.DEEPGRAM_API_KEY
        # Asteria model provides a natural, conversational tone with low latency.
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
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.base_url,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.content


# Global singleton instance for the Aries pipeline motor layer.
tts_adapter = TTSAdapter()
