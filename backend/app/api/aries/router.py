import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.aries.service import aries_service
from app.core.aries.models import VoiceRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def aries_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Aries WebSocket connected")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            req = VoiceRequest(**message)

            text_to_process = req.audio_chunk or ""

            response = await aries_service.process_voice_interaction(
                text_input=text_to_process,
                session_id=req.session_id,
                username=req.username or "anonymous",
                skill_id=req.skill_id,
                code_context=req.code_context,
            )

            await websocket.send_json(response.dict())

    except WebSocketDisconnect:
        logger.info("Aries WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
        await websocket.close()
