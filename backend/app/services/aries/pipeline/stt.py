import os
import json
import asyncio
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)


class STTAdapter:
    def __init__(self):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        self.client = DeepgramClient(self.api_key)

    async def transcribe_stream(self, on_transcript_callback):
        """
        Connects to Deepgram Live and calls the callback with results.
        """
        # Note: This will be used by the Service Layer to handle real-time audio chunks
        options = LiveOptions(
            model="nova-2-general",
            language="en-US",
            smart_format=True,
            interim_results=True,
        )

        # Implementation details will go into service layer integration
        pass


stt_adapter = STTAdapter()
