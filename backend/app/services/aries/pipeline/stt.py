import logging

from app.core.config import settings
from deepgram import AsyncDeepgramClient

logger = logging.getLogger(__name__)


class STTAdapter:
    """Adapter for converting speech audio to text using Deepgram.

    This class provides the 'Sensory Input' layer for the Aries agent,
    allowing it to understand spoken commands. It utilizes the high-performance
    Deepgram Nova-2 model for near-instant transcription.

    Attributes:
        api_key (str): The Deepgram API key for authentication.
        client (AsyncDeepgramClient): The asynchronous Deepgram client instance.
    """

    def __init__(self, api_key: str):
        """Initializes the STTAdapter with the provided API key.

        Args:
            api_key (str): The Deepgram API key.
        """
        self.api_key = api_key
        # In v6.x of the Deepgram SDK, AsyncDeepgramClient is the entry point.
        self.client = AsyncDeepgramClient(api_key=self.api_key)

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
            logger.info(f"STT: Transcribing {len(audio_bytes)} bytes of audio data...")

            # We use the v1 media transcription API for high-performance file-like streams.
            response = await self.client.listen.v("1").media.transcribe_file(
                request=audio_bytes, model="nova-2", smart_format=True, language="en-US"
            )

            # Extract the raw transcript from the nested response structure.
            transcript = (
                response.results.channels[0].alternatives[0].transcript
                if response.results.channels
                else ""
            )

            logger.info(f"STT: Successfully extracted transcript: '{transcript}'")
            return transcript

        except Exception as e:
            logger.error(f"STT_ERROR: Deepgram transcription failed: {e}")
            return ""


# Global singleton instance for the Aries pipeline sensory layer.
stt_adapter = STTAdapter(settings.DEEPGRAM_API_KEY)
