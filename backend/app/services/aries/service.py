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

    async def process_text_interaction(
        self,
        text_input: str,
        session_id: str,
        skill_id: str = "aries-default",
        code_context: str = "",
        username: str = "anonymous",
    ) -> AsyncGenerator[VoiceResponse, None]:
        """Handles a discrete text interaction loop, bypassing STT and TTS.

        Args:
            text_input (str): The raw text input from the user.
            session_id (str): The unique identifier for the user's active session.
            skill_id (str): The specific Aries skill/persona to use.
            code_context (str): The current code in the user's editor.
            username (str): The name of the user for personalized responses.

        Yields:
            VoiceResponse: Incremental updates containing text or actions.
        """
        try:
            start_total = time.time()
            logger.info(f"SERVICE: Starting text interaction for session {session_id}")

            # 1. COGNITION: LangGraph Reasoning Loop
            if code_context:
                await memory_service.set_current_code(session_id, code_context)

            system_prompt = self.skill_manager.get_system_prompt(
                skill_id, code_context or ""
            )

            from langchain_core.messages import HumanMessage
            from app.services.aries.pipeline.graph import get_aries_graph

            aries_graph = await get_aries_graph()
            graph_start = time.time()

            initial_state = {
                "messages": [HumanMessage(content=text_input)],
                "session_id": session_id,
                "username": username,
                "system_prompt": system_prompt,
            }

            ai_text = ""
            async for event in aries_graph.astream(
                initial_state, config={"configurable": {"thread_id": session_id}}
            ):
                for node_name, output in event.items():
                    if node_name == "agent":
                        last_msg = output["messages"][-1]
                        if (
                            not hasattr(last_msg, "tool_calls")
                            or not last_msg.tool_calls
                        ):
                            ai_text = last_msg.content
                    elif node_name == "tools":
                        for tool_msg in output["messages"]:
                            content = getattr(tool_msg, "content", "")
                            if content.startswith("SIGNAL:ACTION:"):
                                parts = content.split(":")
                                action = parts[2]
                                payload = parts[3] if len(parts) > 3 else None
                                yield VoiceResponse(
                                    text="",
                                    action=action,
                                    action_payload={"slug": payload, "view": payload}
                                    if payload
                                    else {},
                                )

            graph_duration = time.time() - graph_start
            if not ai_text:
                ai_text = "I've processed your request. How else can I help?"

            yield VoiceResponse(text=ai_text)

            # Record interaction
            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg=text_input,
                ai_msg=ai_text,
                skill_id=skill_id,
            )

            total_duration = time.time() - start_total
            logger.info(f"SERVICE: Total text interaction took {total_duration:.2f}s")

        except Exception:
            logger.exception("SERVICE_ERROR: Fatal failure in text interaction")
            yield VoiceResponse(text="I'm sorry, I encountered an internal error.")

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

            from langchain_core.messages import HumanMessage

            from app.services.aries.pipeline.graph import get_aries_graph

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
                        # Detect UI signals from tool execution results
                        for tool_msg in output["messages"]:
                            content = getattr(tool_msg, "content", "")
                            if content.startswith("SIGNAL:ACTION:"):
                                parts = content.split(":")
                                action = parts[2]
                                payload = parts[3] if len(parts) > 3 else None
                                logger.info(f"GRAPH: Intercepted UI signal - {action}")
                                yield VoiceResponse(
                                    text="",
                                    action=action,
                                    action_payload={"slug": payload, "view": payload}
                                    if payload
                                    else {},
                                )

            graph_duration = time.time() - graph_start
            logger.info(f"GRAPH: Reasoning loop finished in {graph_duration:.2f}s")

            if not ai_text:
                ai_text = "I've processed your request. How else can I help?"

            # 4. YIELD FINAL RESPONSE
            # No longer using parse_action regex. It's all tool-driven now.
            yield VoiceResponse(text=ai_text)

            # 4. MOTOR OUTPUT: Text-to-Speech
            logger.info("TTS: Generating audio for response...")
            audio_b64_out = None
            try:
                audio_bytes_out = await self.tts.speak(ai_text)
                audio_b64_out = base64.b64encode(audio_bytes_out).decode("utf-8")
            except Exception as tts_err:
                logger.warning(f"TTS_WARNING: Failed to generate audio: {tts_err}")

            # 5. MEMORY CONSOLIDATION
            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg=text_input,
                ai_msg=ai_text,
                skill_id=skill_id,
            )

            # Yield the final audio chunk if available
            if audio_b64_out:
                yield VoiceResponse(text="", audio_chunk=audio_b64_out)

            total_duration = time.time() - start_total
            logger.info(
                f"SERVICE: Total text turn took {total_duration:.2f}s "
                f"(Graph: {graph_duration:.2f}s)"
            )

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
        """Generates a proactive, contextual welcome message for the user using LLM.

        Args:
            session_id (str): The unique identifier for the user session.
            username (str): The name of the user.
            skill_id (str): The skill/persona to use.

        Yields:
            VoiceResponse: Incremental updates for streaming text-and-audio welcome.
        """
        try:
            # Get the skill's system prompt
            system_prompt = self.skill_manager.get_system_prompt(skill_id, "")
            system_prompt += (
                "\n\nCRITICAL: Give a warm, high-energy greeting. "
                "Mention you're ready to dive into some code. "
                "Ask if they want to work on a specific problem or just practice a concept. "
                "Keep it under 20 words. End with a punchy question."
            )

            # Get current problem context from Redis
            problem = await aries_redis.get_current_problem(session_id)
            context_msg = ""
            if problem:
                title = problem.get("title", "this problem")
                context_msg = f" The user is working on {title}."

            # Call LLM directly for quick welcome (bypass full graph)
            response = await self.brain.generate_response(
                text=f"Welcome the user briefly.{context_msg}",
                system_prompt=system_prompt,
                provider="groq",
            )
            ai_text = (
                response.strip() if isinstance(response, str) else str(response).strip()
            )
            # Yield the greeting text immediately
            yield VoiceResponse(text=ai_text)

            # Generate TTS audio
            try:
                audio_bytes = await self.tts.speak(ai_text)
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                yield VoiceResponse(text="", audio_chunk=audio_b64)
                logger.info(f"SERVICE: TTS audio sent ({len(audio_bytes)} bytes)")
            except Exception as e:
                logger.warning(f"TTS_WARNING: Could not generate audio: {e}")

            # Record the greeting
            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg="[SYSTEM_EVENT: WELCOME]",
                ai_msg=ai_text,
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
