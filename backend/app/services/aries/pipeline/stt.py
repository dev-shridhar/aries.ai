import logging

from deepgram import DeepgramClient, FileSource, PrerecordedOptions

from app.core.config import settings

logger = logging.getLogger(__name__)


class STTAdapter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # In v3, DeepgramClient is the entry point
        self.client = DeepgramClient(self.api_key)

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribes audio bytes to text using Deepgram."""
        if not audio_bytes:
            return ""

        try:
            logger.info(f"STT: Transcribing {len(audio_bytes)} bytes...")

            payload = {"buffer": audio_bytes}
            options = PrerecordedOptions(
                model="nova-2",
                smart_format=True,
            )

            # Use the async REST client for pre-recorded audio
            response = await self.client.listen.asyncrest.v("1").transcribe_file(
                payload, options
            )

            transcript = (
                response.results.channels[0].alternatives[0].transcript
                if response.results.channels
                else ""
            )
            logger.info(f"STT: Extracted transcript: '{transcript}'")
            return transcript
        except Exception as e:
            logger.error(f"STT: Deepgram transcription failed: {e}")
            return ""


stt_adapter = STTAdapter(settings.DEEPGRAM_API_KEY)
