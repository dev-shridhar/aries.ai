import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.core.voice.models import TTSRequest
from app.services.voice.service import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    try:
        audio_content = await VoiceService.synthesize_speech(req.text)
        return Response(content=audio_content, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")
