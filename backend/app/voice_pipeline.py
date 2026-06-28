import base64
import logging
from groq import AsyncGroq
from deepgram import DeepgramClient, PrerecordedOptions
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class VoicePipeline:
    def __init__(self):
        self.groq = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.deepgram = DeepgramClient(settings.DEEPGRAM_API_KEY)

    async def stt(self, audio: bytes) -> str:
        options = PrerecordedOptions(model="nova-2", smart_format=True)
        response = await self.deepgram.listen.asyncrest.v("1").transcribe_file(
            {"buffer": audio}, options
        )
        return response.results.channels[0].alternatives[0].transcript or ""

    async def brain(self, text: str, system: str, history: list[dict]) -> str:
        messages = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": text})
        completion = await self.groq.chat.completions.create(
            messages=messages, model=settings.BRAIN_MODEL, timeout=15
        )
        return completion.choices[0].message.content

    async def tts(self, text: str) -> bytes:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=linear16&container=wav",
                headers={"Authorization": f"Token {settings.DEEPGRAM_API_KEY}", "Content-Type": "application/json"},
                json={"text": text},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.content

    async def process(self, audio: bytes, system: str, history: list[dict]) -> tuple[str, str, bytes]:
        text = await self.stt(audio)
        if not text.strip():
            return "", "", b""
        reply = await self.brain(text, system, history)
        audio_out = await self.tts(reply)
        return text, reply, audio_out


pipeline = VoicePipeline()
