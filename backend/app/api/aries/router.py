import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.aries.models import VoiceRequest, VoiceResponse
from app.services.aries.service import aries_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def aries_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Aries WebSocket connected for streaming")

    # State for the session
    state = {
        "session_id": "default-session",
        "username": "anonymous",
        "skill_id": "aries-default",
        "code_context": "",
        "audio_buffer": b"",
    }

    try:
        while True:
            # Handle both text (config/legacy) and binary (audio)
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                logger.info("Aries WebSocket disconnected gracefully")
                break

            if "text" in message:
                data = json.loads(message["text"])
                logger.debug(f"Received JSON message keys: {list(data.keys())}")
                # Update session state if provided
                if "session_id" in data:
                    state["session_id"] = data["session_id"]
                if "username" in data:
                    state["username"] = data["username"]
                if "code_context" in data:
                    state["code_context"] = data["code_context"]

                if data.get("event") == "WELCOME":
                    logger.info(
                        "ROUTER: Received WELCOME event from UI. Triggering welcome interaction..."
                    )
                    async for response in aries_service.process_welcome_interaction(
                        session_id=state["session_id"], username=state["username"]
                    ):
                        await websocket.send_json(response.dict())

                # TRIGGER: Process the buffered audio
                if data.get("event") == "PROCESS_AUDIO":
                    logger.info(
                        f"ROUTER: Received PROCESS_AUDIO event. Waiting 200ms for trailing chunks..."
                    )
                    await asyncio.sleep(
                        0.2
                    )  # Grace period for trailing binary messages

                    logger.info(
                        f"ROUTER: Final buffer size: {len(state['audio_buffer'])} bytes."
                    )

                    if not state["audio_buffer"]:
                        await websocket.send_json(VoiceResponse(text="").dict())
                    else:
                        try:
                            async for (
                                response
                            ) in aries_service.process_voice_interaction(
                                audio_bytes=state["audio_buffer"],
                                session_id=state["session_id"],
                                username=state["username"],
                                skill_id=state.get("skill_id", state["skill_id"]),
                                code_context=state["code_context"],
                            ):
                                await websocket.send_json(response.dict())
                            state["audio_buffer"] = b""  # Clear for next turn
                        except Exception as e:
                            logger.error(f"ROUTER: Service processing failed: {e}")
                            await websocket.send_json(
                                VoiceResponse(text="Error processing audio.").dict()
                            )

            elif "bytes" in message:
                # Accumulate audio bytes
                state["audio_buffer"] += message["bytes"]
                logger.debug(
                    f"ROUTER: Buffered {len(message['bytes'])} bytes. Total: {len(state['audio_buffer'])}"
                )

    except WebSocketDisconnect:
        logger.info("Aries WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
