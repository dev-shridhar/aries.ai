import base64
import logging
import time
from collections.abc import AsyncGenerator

from app.core.aries.models import VoiceResponse
from app.infrastructure.aries.redis_client import aries_redis
from app.services.aries.actions.triggers import action_trigger
from app.services.aries.memory import memory_service
from app.services.aries.pipeline.brain import brain_adapter
from app.services.aries.pipeline.stt import stt_adapter
from app.services.aries.pipeline.tts import tts_adapter
from app.services.aries.skills.manager import skill_manager

logger = logging.getLogger(__name__)


class AriesService:
    """Core orchestrator for the Aries autonomous voice agent.

    AriesService manages the high-level coordination between perception (STT),
    cognition (LangGraph/Brain), and motor output (TTS). It adheres to a
    Vertical Slice architecture, focusing on providing a seamless, low-latency
    voice experience for coding assistance.
    """

    def __init__(self):
        """Initializes the AriesService with its dependent adapters."""
        self.skill_manager = skill_manager
        self.brain = brain_adapter
        self.stt = stt_adapter
        self.tts = tts_adapter
        self.actions = action_trigger

    async def process_voice_interaction(
        self,
        audio_bytes: bytes,
        session_id: str,
        skill_id: str = "aries-default",
        code_context: str = "",
        username: str = "anonymous",
    ) -> AsyncGenerator[VoiceResponse, None]:
        """Handles a complete discrete voice interaction loop.

        This method executes the 'Audio -> STT -> Brain -> TTS -> Audio' pipeline.
        It uses a streaming approach to yield intermediate results (transcripts)
        to the user as quickly as possible, reducing perceived latency.

        Args:
            audio_bytes (bytes): The raw audio input from the user.
            session_id (str): The unique identifier for the user's active session.
            skill_id (str): The specific Aries skill/persona to use.
            code_context (str): The current code in the user's editor.
            username (str): The name of the user for personalized responses.

        Yields:
            VoiceResponse: Incremental updates containing transcript, text,
                actions, or audio chunks.
        """
        try:
            start_total = time.time()
            logger.info(f"SERVICE: Starting voice interaction for session {session_id}")

            # 1. PERCEPTION: Speech-to-Text
            if not audio_bytes:
                logger.warning("SERVICE: Received empty audio buffer.")
                yield VoiceResponse(text="I'm listening, but I didn't hear anything.")
                return

            stt_start = time.time()
            text_input = await self.stt.transcribe(audio_bytes)
            stt_duration = time.time() - stt_start

            logger.info(
                f"STT: Finished in {stt_duration:.2f}s. Transcript: '{text_input}'"
            )

            # Immediately yield the transcript to show the user we heard them.
            yield VoiceResponse(text=text_input, is_final=True, speech_final=False)

            # 1.1 NOISE FILTERING
            if self._is_noise(text_input):
                logger.info("SERVICE: Noise or silence detected. Skipping reasoning.")
                yield VoiceResponse(text="")
                return

            # 2. COGNITION: LangGraph Reasoning Loop
            # We synchronize the immediate sensory state before running the graph.
            if code_context:
                await memory_service.set_current_code(session_id, code_context)

            # Fetch the persona-based system prompt
            system_prompt = self.skill_manager.get_system_prompt(
                skill_id, code_context or ""
            )
            system_prompt += (
                "\n\nCRITICAL: You are an autonomous agent with ZERO initial context "
                "in your prompt. You MUST use your tools (get_recent_history, "
                "get_current_state, search_memory_palace) to see what is happening. "
                "Never guess about the user's state or code."
            )

            from app.services.aries.pipeline.graph import get_aries_graph
            from langchain_core.messages import HumanMessage

            aries_graph = await get_aries_graph()
            graph_start = time.time()

            initial_state = {
                "messages": [HumanMessage(content=text_input)],
                "session_id": session_id,
                "username": username,
                "system_prompt": system_prompt,
            }

            ai_text = ""
            # Execute the cyclic reasoning graph
            async for event in aries_graph.astream(
                initial_state, config={"configurable": {"thread_id": session_id}}
            ):
                for node_name, output in event.items():
                    if node_name == "agent":
                        last_msg = output["messages"][-1]
                        # Capture the final text response if no more tool calls
                        if (
                            not hasattr(last_msg, "tool_calls")
                            or not last_msg.tool_calls
                        ):
                            ai_text = last_msg.content
                    elif node_name == "tools":
                        logger.info("GRAPH: Autonomous tool execution completed.")

            graph_duration = time.time() - graph_start
            logger.info(f"GRAPH: Reasoning loop finished in {graph_duration:.2f}s")

            if not ai_text:
                ai_text = "I've processed your request. How else can I help?"

            # 3. ACTION DISPATCHING (Backward Compatibility)
            # Many actions are now tools in the graph, but some UI-only triggers remain.
            action_data = self.actions.parse_action(ai_text)

            # Yield the final text and any parsed actions
            yield VoiceResponse(
                text=ai_text,
                action=action_data["action"] if action_data else None,
                action_payload=action_data["payload"] if action_data else None,
            )

            # 4. MOTOR OUTPUT: Text-to-Speech
            logger.info("TTS: Generating audio for response...")
            try:
                audio_bytes_out = await self.tts.speak(ai_text)
                audio_b64_out = base64.b64encode(audio_bytes_out).decode("utf-8")
            except Exception as tts_err:
                logger.error(f"TTS_ERROR: Failed to generate audio: {tts_err}")
                audio_b64_out = None

            # 5. MEMORY CONSOLIDATION
            # Record the interaction for long-term recall and contextual continuity.
            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg=text_input,
                ai_msg=ai_text,
                skill_id=skill_id,
            )

            # If the response triggered a manual fact recording action
            if action_data and action_data["action"] == "RECORD_FACT":
                payload = action_data["payload"]
                await memory_service.record_user_fact(
                    username=username,
                    concept=payload["concept"],
                    value=payload["value"],
                )

            # Yield the final audio chunk
            yield VoiceResponse(text="", audio_chunk=audio_b64_out)

            total_duration = time.time() - start_total
            logger.info(f"SERVICE: Total voice pipeline took {total_duration:.2f}s")

        except Exception:
            logger.exception(
                "SERVICE_ERROR: Fatal failure in voice interaction pipeline"
            )
            yield VoiceResponse(
                text="I'm sorry, I encountered a temporary logic failure."
            )

    async def process_welcome_interaction(
        self,
        session_id: str,
        username: str = "anonymous",
        skill_id: str = "aries-default",
    ) -> AsyncGenerator[VoiceResponse, None]:
        """Generates a proactive, contextual welcome message for the user.

        Args:
            session_id (str): The unique identifier for the user session.
            username (str): The name of the user.
            skill_id (str): The skill/persona to use.

        Yields:
            VoiceResponse: Incremental updates for streaming text-and-audio welcome.
        """
        try:
            # Check the current problem state in Redis to customize the greeting.
            problem = await aries_redis.get_current_problem(session_id)

            if problem:
                title = problem.get("title", "this problem")
                welcome_prompt = (
                    f"You are Aries. The user is currently looking at '{title}'. "
                    "Briefly greet them (15 words max) and ask if they need help with the logic."
                )
            else:
                welcome_prompt = (
                    "You are Aries. The user hasn't loaded a problem yet. "
                    "Briefly greet them (15 words max) and suggest starting with a simple challenge."
                )

            logger.info(f"SERVICE: Generating welcome for session {session_id}")

            full_text = ""
            sentence_buffer = ""

            # Use the brain adapter directly for streaming welcome (no tool calling needed here).
            async for chunk in self.brain.generate_response_stream(
                "System: Introduce yourself to the user.",
                welcome_prompt,
                history=[],
            ):
                full_text += chunk
                sentence_buffer += chunk

                yield VoiceResponse(text=chunk)

                # Stream audio by sentence boundaries to reduce time-to-first-sound.
                if (
                    any(p in chunk for p in (".", "?", "!"))
                    and len(sentence_buffer) > 15
                ):
                    audio_bytes = await self.tts.speak(sentence_buffer.strip())
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    yield VoiceResponse(text="", audio_chunk=audio_b64)
                    sentence_buffer = ""

            # Flush the remaining buffer
            if sentence_buffer.strip():
                audio_bytes = await self.tts.speak(sentence_buffer.strip())
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                yield VoiceResponse(text="", audio_chunk=audio_b64)

            # Record the greeting in memory so Aries knows it already said 'hello'.
            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg="[SYSTEM_EVENT: WELCOME]",
                ai_msg=full_text,
                skill_id=skill_id,
            )

        except Exception as e:
            logger.error(f"SERVICE_ERROR: Welcome message generation failed: {e}")

    def _is_noise(self, text: str) -> bool:
        """Determines if the transcribed text is likely background noise or silence."""
        if not text:
            return True
        clean_text = text.strip().lower().rstrip(".,!?")
        # Filter typical low-entropy STT artifacts.
        if len(clean_text) < 2 or clean_text in ["it", "it is", "the", "um", "uh"]:
            return True
        return False


# Global singleton instance of the Aries service.
aries_service = AriesService()
