import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GroqSTTAdapter:
    """Adapter for converting speech audio to text using Groq Whisper.

    This class provides the 'Sensory Input' layer for the Aries agent,
    allowing it to understand spoken commands. It utilizes the high-performance
    Groq Whisper Large V3 Turbo model for near-instant transcription.

    Attributes:
        api_key (str): The Groq API key for authentication.
    """

    def __init__(self, api_key: str):
        """Initializes the GroqSTTAdapter with the provided API key.

        Args:
            api_key (str): The Groq API key.
        """
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribes raw audio bytes into a text string.

        This method sends the audio data to Groq's Whisper model for fast transcription.

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
                f"GROQ_STT: Transcribing {len(audio_bytes)} bytes of audio data..."
            )

            # Detect audio format from magic bytes
            if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
                filename = "audio.wav"
                content_type = "audio/wav"
            elif audio_bytes[:4] == b"fLaC":
                filename = "audio.flac"
                content_type = "audio/flac"
            elif audio_bytes[:4] == b"ID3":
                # Likely mp3
                filename = "audio.mp3"
                content_type = "audio/mpeg"
            else:
                # Default to webm/ogg which is what browsers send
                filename = "audio.webm"
                content_type = "audio/webm"

            files = {
                "file": (filename, audio_bytes, content_type),
            }
            data = {
                "model": "whisper-large-v3-turbo",
                "language": "en",
                "response_format": "json",
                "temperature": "0.0",
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    files=files,
                    data=data,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                result = response.json()

            transcript = result.get("text", "")
            logger.info(f"GROQ_STT: Successfully extracted transcript: '{transcript}'")
            return transcript

        except Exception as e:
            logger.error(f"GROQ_STT_ERROR: Groq transcription failed: {e}")
            logger.error(
                f"GROQ_STT_ERROR: Audio bytes first 20: {audio_bytes[:20] if audio_bytes else 'empty'}"
            )
            logger.error(
                f"GROQ_STT_ERROR: Detected format - filename: {filename}, content_type: {content_type}"
            )
            return ""


# Global singleton instance for Groq STT.
groq_stt_adapter = GroqSTTAdapter(settings.GROQ_API_KEY)
