import logging
import json
import random
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.aries.service import aries_service
from app.services.aries.pipeline.stt import stt_adapter
from app.services.aries.pipeline.tts import tts_adapter

logger = logging.getLogger(__name__)
router = APIRouter()

WAKE_MESSAGES = [
    "Hey there! I'm Delia, your coding companion. What would you like to work on today?",
    "Hi! I'm Delia, ready to help you code. What are we building?",
    "Hey! Delia here. I can help you solve LeetCode problems, write code, or answer questions. What do you need?",
    "Hello! I'm your AI coding buddy. Tell me what you'd like to work on - maybe a coding problem or some help debugging?",
    "Hey there! I'm Delia. I can load problems, run your code, or just chat about coding. What shall we do?",
]


async def send_wake_message(websocket: WebSocket):
    """Send a random hardcoded wake message."""
    msg = random.choice(WAKE_MESSAGES)
    logger.info(f"Sending wake message: {msg}")

    audio_bytes = await tts_adapter.speak(msg)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    await websocket.send_json({"action": "SENSORY: WAKE", "text": msg})
    await websocket.send_json({"audio_chunk": audio_b64})


@router.websocket("/ws")
async def aries_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Aries WebSocket connected")

    state = {
        "session_id": "default-session",
        "username": "anonymous",
        "skill_id": "aries-default",
        "code_context": "",
    }

    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                data = json.loads(message["text"])
                logger.debug(f"Received JSON message keys: {list(data.keys())}")

                if "session_id" in data:
                    state["session_id"] = data["session_id"]
                if "username" in data:
                    state["username"] = data["username"]
                if "code_context" in data:
                    state["code_context"] = data["code_context"]

                # Handle complete audio chunk
                if "audio_chunk" in data:
                    logger.info("Processing complete audio chunk")
                    await websocket.send_json({"action": "SENSORY: PROCESSING"})

                    try:
                        audio_b64 = data["audio_chunk"]
                        audio_bytes = base64.b64decode(audio_b64)

                        # Transcribe
                        transcript = await stt_adapter.transcribe(audio_bytes)
                        logger.info(f"Transcript: '{transcript}'")

                        if not transcript.strip():
                            txt = "I didn't catch that. Try again?"
                            audio_bytes_out = await tts_adapter.speak(txt)
                            audio_b64_out = base64.b64encode(audio_bytes_out).decode(
                                "utf-8"
                            )
                            await websocket.send_json({"text": txt})
                            await websocket.send_json({"audio_chunk": audio_b64_out})
                            continue

                        await websocket.send_json(
                            {"text": transcript, "is_final": True}
                        )

                        # Check for wake word
                        if "hey aries" in transcript.lower():
                            await send_wake_message(websocket)
                            continue

                        # Process through brain
                        async for (
                            response
                        ) in aries_service.process_streaming_interaction(
                            text_input=transcript,
                            session_id=state["session_id"],
                            username=state["username"],
                            skill_id=state["skill_id"],
                            code_context=state["code_context"],
                        ):
                            await websocket.send_json(response.dict())

                    except Exception as e:
                        logger.exception("Error processing audio")
                        await websocket.send_json(
                            {"text": "Oops, something went wrong."}
                        )

                # Handle text input (e.g., from mascot click)
                elif "text" in data and data.get("text"):
                    text_input = data["text"]
                    logger.info(f"Received text input: '{text_input}'")

                    # Check for wake word
                    if "hey aries" in text_input.lower():
                        await send_wake_message(websocket)
                        continue

                    async for response in aries_service.process_streaming_interaction(
                        text_input=text_input,
                        session_id=state["session_id"],
                        username=state["username"],
                        skill_id=state["skill_id"],
                        code_context=state["code_context"],
                    ):
                        await websocket.send_json(response.dict())

    except WebSocketDisconnect:
        logger.info("Aries WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
