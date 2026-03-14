import httpx
from app.core.config import settings


class TTSAdapter:
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
        self.base_url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=linear16&container=wav"

    async def speak(self, text: str) -> bytes:
        """
        Converts text to speech audio bytes using Deepgram Aura.
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


tts_adapter = TTSAdapter()
