import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.aries.models import VoiceResponse
from app.infrastructure.aries.redis_client import aries_redis
from app.services.aries.service import aries_service

logger = logging.getLogger(__name__)
router = APIRouter()


class ProblemState(BaseModel):
    session_id: str
    username: str = "anonymous"
    problem_slug: str | None = None
    problem_title: str | None = None
    problem_difficulty: str | None = None


@router.post("/problem-state")
async def set_problem_state(state: ProblemState):
    """Stores the current problem state in Redis for the agent to access."""
    if state.problem_slug:
        problem_data: dict = {
            "slug": state.problem_slug,
            "title": state.problem_title,
            "difficulty": state.problem_difficulty,
        }
        await aries_redis.set_current_problem(state.session_id, problem_data)
        logger.info(f"ROUTER: Set problem state - {state.problem_slug}")
    else:
        logger.info(f"ROUTER: Cleared problem state")
    return {"status": "ok"}


@router.websocket("/ws")
async def aries_websocket(websocket: WebSocket) -> None:
    """The primary WebSocket entry point for the Aries voice agent.

    This endpoint manages the full-duplex communication stream between the
    UI and the reasoning engine. It handles:
    1.  **Session Initialization**: Syncing username and session IDs.
    2.  **Sensory Input**: Accumulating binary audio chunks from the microphone.
    3.  **Proactive Events**: Handling 'WELCOME' triggers from the UI.
    4.  **Cognitive Execution**: Orchestrating the processing of audio turns
        via the AresService.

    Args:
        websocket (WebSocket): The active FastAPI connection.
    """
    await websocket.accept()
    logger.info("ROUTER: Aries WebSocket session established.")

    # Volatile session state (Sensory State)
    # This state exists for the duration of the WebSocket connection.
    state: dict[str, Any] = {
        "session_id": "default-session",
        "username": "anonymous",
        "skill_id": "aries-default",
        "code_context": "",
        "audio_buffer": b"",
    }

    try:
        while True:
            # The router handles a multiplexed stream of JSON metadata
            # and raw binary audio chunks.
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                logger.info("ROUTER: WebSocket disconnected")
                break

            # Log all message types
            msg_keys = list(message.keys())
            logger.info(f"ROUTER: Received message type: {msg_keys}")

            # CASE 1: JSON METADATA (Configuration or Events)
            if "text" in message:
                data = json.loads(message["text"])
                logger.debug(f"ROUTER: Protocol message received: {list(data.keys())}")

                # Update session state if provided by the UI.
                if "session_id" in data:
                    state["session_id"] = data["session_id"]
                if "username" in data:
                    state["username"] = data["username"]
                if "code_context" in data:
                    state["code_context"] = data["code_context"]
                if "skill_id" in data:
                    state["skill_id"] = data["skill_id"]

                # Handle Proactive 'WELCOME' Event
                if data.get("event") == "WELCOME":
                    logger.info("ROUTER: UI triggered WELCOME event.")
                    async for response in aries_service.process_welcome_interaction(
                        session_id=state["session_id"], username=state["username"]
                    ):
                        response_dict = response.dict()
                        text_preview = (
                            response_dict.get("text", "")[:50]
                            if response_dict.get("text")
                            else "None"
                        )
                        has_audio = "yes" if response_dict.get("audio_chunk") else "no"
                        logger.info(
                            f"ROUTER: Sending welcome response - text: {text_preview}, audio: {has_audio}"
                        )
                        await websocket.send_json(response_dict)

                # Handle Cognitive 'PROCESS_AUDIO' Event
                if data.get("event") == "PROCESS_AUDIO":
                    # We wait a brief moment to allow trailing binary chunks
                    # to arrive before starting the heavy reasoning phase.
                    await asyncio.sleep(0.2)

                    logger.info(
                        f"ROUTER: Finalizing turn. Buffer size: {len(state['audio_buffer'])} bytes."  # noqa: E501
                    )

                    if not state["audio_buffer"]:
                        logger.warning(
                            "ROUTER: No audio buffer - sending empty response"
                        )
                        # Send an empty success signal if no audio was received.
                        await websocket.send_json(VoiceResponse(text="").dict())
                    else:
                        try:
                            # Pass the accumulated sensory data to the orchestrator.
                            async for (
                                response
                            ) in aries_service.process_voice_interaction(
                                audio_bytes=state["audio_buffer"],
                                session_id=state["session_id"],
                                username=state["username"],
                                skill_id=state["skill_id"],
                                code_context=state["code_context"],
                            ):
                                await websocket.send_json(response.dict())

                            # Clear sensory buffer for the next user turn.
                            state["audio_buffer"] = b""
                        except Exception as e:
                            logger.error(f"ROUTER: Reasoning engine failure: {e}")
                            await websocket.send_json(
                                VoiceResponse(
                                    text="I'm sorry, I encountered a cognitive error during processing."  # noqa: E501
                                ).dict()
                            )

            # CASE 2: BINARY AUDIO (Transcription Chunks)
            elif "bytes" in message:
                chunk_size = len(message["bytes"])
                state["audio_buffer"] += message["bytes"]
                magic = message["bytes"][:10].hex()
                logger.info(
                    f"ROUTER: Received audio chunk ({chunk_size}B). Magic: {magic}. Total: {len(state['audio_buffer'])}B"
                )
            else:
                # Log unknown message type for debugging
                logger.warning(
                    f"ROUTER: Unknown message type: {message.get('type')}, keys: {list(message.keys())}"
                )

    except WebSocketDisconnect:
        logger.info("ROUTER: WebSocket disconnected gracefully.")
    except Exception:
        logger.exception("ROUTER: Unexpected transport failure.")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("ROUTER: Session terminated.")
