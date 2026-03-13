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
    logger.info("Aries WebSocket connected for streaming")

    from app.services.aries.pipeline.stt import stt_adapter

    # State for the session
    state = {
        "session_id": "default-session",
        "username": "anonymous",
        "skill_id": "aries-default",
        "code_context": "",
    }

    async def on_transcript(transcript: str, is_final: bool, speech_final: bool):
        # 1. Send partial transcript to UI
        await websocket.send_json(
            {"text": transcript, "is_final": is_final, "speech_final": speech_final}
        )

        # 2. Wake Word Detection ("Hey Aries" or "Aries")
        trigger_now = speech_final
        is_wake = False
        
        lowercase_transcript = transcript.lower().strip()
        if not speech_final and ("hey aries" in lowercase_transcript or lowercase_transcript.startswith("aries")):
            # If they say "Hey Aries", we don't necessarily wait for speech_final if they pause
            # But for simplicity, we'll just check if it's in the transcript and if they haven't spoken much else
            logger.info("Wake word detected!")
            is_wake = True
            # Transition frontend to active state
            await websocket.send_json({"action": "SENSORY: WAKE"})

        # 3. If sentence is actually finished, trigger the Brain
        if speech_final or is_wake:
            logger.info(f"Triggering Brain with transcript: '{transcript}'")
            async for response in aries_service.process_streaming_interaction(
                text_input=transcript,
                session_id=state["session_id"],
                username=state["username"],
                skill_id=state["skill_id"],
                code_context=state["code_context"],
            ):
                await websocket.send_json(response.dict())

    # Initialize Deepgram Live Connection
    dg_connection = await stt_adapter.get_streaming_connection(on_transcript)

    try:
        while True:
            # Handle both text (config/legacy) and binary (audio)
            message = await websocket.receive()

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
                
                # Check for EVENT: WELCOME
                if data.get("event") == "WELCOME":
                    logger.info("ROUTER: Received WELCOME event from UI. Triggering welcome interaction...")
                    async for response in aries_service.process_welcome_interaction(
                        session_id=state["session_id"],
                        username=state["username"]
                    ):
                        await websocket.send_json(response.dict())

                # If it contains an audio_chunk (legacy/batch), process it normally
                if "audio_chunk" in data:
                    logger.info("Received legacy batch audio via WebSocket")
                    response = await aries_service.process_voice_interaction(
                        audio_b64=data["audio_chunk"],
                        session_id=state["session_id"],
                        username=state["username"],
                        skill_id=data.get("skill_id", state["skill_id"]),
                        code_context=state["code_context"],
                    )
                    await websocket.send_json(response.dict())

            elif "bytes" in message:
                # Stream raw audio to Deepgram
                logger.debug(f"ROUTER: Received {len(message['bytes'])} bytes of audio. Streaming to DG.")
                await dg_connection.send(message["bytes"])

    except WebSocketDisconnect:
        logger.info("Aries WebSocket disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
    finally:
        await dg_connection.finish()
        try:
            await websocket.close()
        except Exception:
            pass
