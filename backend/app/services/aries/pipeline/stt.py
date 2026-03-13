import logging
import asyncio
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
from app.core.config import settings

logger = logging.getLogger(__name__)


class STTAdapter:
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
        # Use the standard DeepgramClient for v3
        self.client = DeepgramClient(api_key=self.api_key)

    async def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribes audio bytes using Deepgram's pre-recorded API.
        """
        try:
            # Deepgram v3 stable syntax
            response = await self.client.listen.asyncprerecorded.v("1").transcribe_file(
                {"buffer": audio_bytes}, 
                {"model": "nova-2-general", "smart_format": True}
            )

            transcript = response.results.channels[0].alternatives[0].transcript
            return transcript or ""
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"STT Transcription Error: {e}")
            return ""

    async def get_streaming_connection(self, on_transcript):
        """
        Establishes a persistent streaming connection to Deepgram.
        """
        logger.info("Initializing Deepgram streaming connection...")
        options = LiveOptions(
            model="nova-2-general",
            language="en-US",
            smart_format=True,
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
        )

        try:
            # Standard v3 versioned streaming connection
            dg_connection = self.client.listen.asyncwebsocket.v("1")

            async def on_message(*args, **kwargs):
                try:
                    # Deepgram usually passes (self, result, **kwargs) or (result, **kwargs)
                    # We'll check args for the result object.
                    result = None
                    if len(args) > 1:
                        result = args[1]
                    elif len(args) > 0:
                        result = args[0]
                    else:
                        result = kwargs.get('result')

                    if result:
                        # Handle both object and dict result formats
                        try:
                            if hasattr(result, 'channel'):
                                transcript = result.channel.alternatives[0].transcript
                                is_final = result.is_final
                                speech_final = result.speech_final
                            else:
                                # Dictionary fallback
                                transcript = result.get('channel', {}).get('alternatives', [{}])[0].get('transcript', '')
                                is_final = result.get('is_final', False)
                                speech_final = result.get('speech_final', False)

                            if transcript:
                                logger.info(f"STT Transcript Parsed: '{transcript}' (final={is_final}, speech={speech_final})")
                                asyncio.create_task(on_transcript(transcript, is_final, speech_final))
                        except Exception as parse_err:
                            logger.error(f"Error extracting transcript from result: {parse_err}. Result: {result}")
                except Exception as e:
                    logger.error(f"Error parsing Deepgram message: {e}")

            async def on_metadata(*args, **kwargs):
                metadata = args[1] if len(args) > 1 else (args[0] if len(args) > 0 else kwargs.get('metadata'))
                logger.info(f"Deepgram Metadata received: {metadata}")

            async def on_error(*args, **kwargs):
                error = args[1] if len(args) > 1 else (args[0] if len(args) > 0 else kwargs.get('error'))
                logger.error(f"Deepgram Streaming Error event: {error}")

            # Register listeners with BOTH enum and string literals for safety
            dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
            dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
            dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            
            # Low-level strings just in case
            dg_connection.on("Transcript", on_message)
            dg_connection.on("Metadata", on_metadata)
            dg_connection.on("Error", on_error)

            # Start the connection
            logger.info("Starting Deepgram streaming connection...")
            
            await dg_connection.start(options)
            logger.info("Deepgram streaming connection started successfully.")
            return dg_connection

        except Exception as e:
            logger.exception(f"Failed to initialize Deepgram connection: {e}")
            raise


stt_adapter = STTAdapter()
