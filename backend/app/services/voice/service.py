import os
import httpx

class VoiceService:
    """Service for interacting with Deepgram TTS/STT APIs."""
    
    @staticmethod
    async def synthesize_speech(text: str) -> bytes:
        """Convert text to speech audio bytes using Deepgram."""
        api_key = os.environ.get("DEEPGRAM_API_KEY")
        if not api_key:
            raise Exception("DEEPGRAM_API_KEY not configured")
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/speak?model=aura-asteria-en",
                headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
                json={"text": text},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.content
