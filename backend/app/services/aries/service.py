import asyncio
import base64
import json
import logging
import re
import time

from app.core.aries.models import VoiceResponse
from app.services.aries.actions.triggers import action_trigger
from app.services.aries.memory import memory_service
from app.services.aries.pipeline.brain import brain_adapter
from app.services.aries.pipeline.stt import stt_adapter
from app.services.aries.pipeline.tts import tts_adapter
from app.services.aries.skills.manager import skill_manager

logger = logging.getLogger(__name__)


class AriesService:
    """
    Core orchestrator for the Aries voice agent.
    Handles the end-to-end pipeline: STT -> Brain (LLM) -> Memory -> TTS.
    """

    def __init__(self):
        self.skill_manager = skill_manager
        self.brain = brain_adapter
        self.tts = tts_adapter
        self.actions = action_trigger
        # STT is handled directly via stt_adapter import/inject if needed,
        # but common practice here seems to be using the adapter directly
        # or keeping it as an instance var.
        from app.services.aries.pipeline.stt import stt_adapter

        self.stt = stt_adapter

    async def process_voice_interaction(
        self,
        audio_bytes: bytes,
        session_id: str,
        skill_id: str = "aries-default",
        code_context: str = "",
        username: str = "anonymous",
    ):
        """
        Full discrete voice loop: Audio -> STT -> Brain -> Memory -> TTS -> Audio.
        Refactored to yield multiple times for streaming feel.
        """
        try:
            import time

            start_total = time.time()
            logger.info(
                f"SERVICE: process_voice_interaction entry. Session: {session_id}, Bytes: {len(audio_bytes)}"
            )

            # 1. Transcribe (Batch STT)
            if not audio_bytes:
                logger.warning("SERVICE: No audio bytes received.")
                yield VoiceResponse(text="I'm listening, but I didn't hear anything.")
                return

            stt_start = time.time()
            try:
                text_input = await self.stt.transcribe(audio_bytes)
            except Exception as stt_err:
                logger.error(f"SERVICE: STT Transcription failed: {stt_err}")
                yield VoiceResponse(
                    text="I had trouble hearing you. Could you repeat that?"
                )
                return

            stt_end = time.time()
            logger.info(
                f"STT Took: {stt_end - stt_start:.2f}s. Transcript: '{text_input}'"
            )

            # --- STREAM POINT 0: Show the user what we heard immediately ---
            yield VoiceResponse(
                text=text_input,
                is_final=True,  # Mark as STT result for frontend
                speech_final=False,  # Keep it until brain response clears it
            )

            # 1.5 Noise/Silence Check
            if self._is_noise(text_input):
                logger.info("Noise or silence detected, skipping brain.")
                yield VoiceResponse(text="")
                return

            # 2. Fetch Unified Context
            context = await memory_service.get_full_context(
                session_id, username, text_input, skill_id
            )

            # 3. Build System Prompt (includes Name check & Memory Palace)
            system_prompt = await self._build_system_prompt(
                skill_id, code_context, context
            )

            # 3.5 Sync Sensory memory (Code)
            if code_context:
                await memory_service.set_current_code(session_id, code_context)

            # 4. Query Brain
            from app.core.config import settings

            logger.info(
                f"Querying Brain ({settings.BRAIN_MODEL}) with transcript: '{text_input}'"
            )
            brain_start = time.time()
            try:
                ai_text = await self.brain.generate_response(
                    text_input,
                    system_prompt,
                    history=context["history"],
                    provider=settings.BRAIN_PROVIDER,
                    model=settings.BRAIN_MODEL,
                )
            except Exception as brain_err:
                logger.error(f"SERVICE: Brain generation failed: {brain_err}")
                ai_text = "I'm having trouble thinking right now. Let's try again."

            brain_end = time.time()
            logger.info(
                f"Brain Took: {brain_end - brain_start:.2f}s. Response: '{ai_text}'"
            )

            # --- STREAM POINT 1: Yield text immediately to clear Thinking state ---
            action_data = self.actions.parse_action(ai_text)

            yield VoiceResponse(
                text=ai_text,
                action=action_data["action"] if action_data else None,
                action_payload=action_data["payload"] if action_data else None,
            )

            # 5. Generate Audio (TTS)
            logger.info("Generating Speech via TTS...")
            tts_start = time.time()
            try:
                audio_bytes_out = await self.tts.speak(ai_text)
            except Exception as tts_err:
                logger.error(f"SERVICE: TTS generation failed: {tts_err}")
                audio_bytes_out = b""  # Fallback to text only

            tts_end = time.time()
            logger.info(f"TTS Took: {tts_end - tts_start:.2f}s")

            audio_b64_out = (
                base64.b64encode(audio_bytes_out).decode("utf-8")
                if audio_bytes_out
                else None
            )

            total_time = time.time() - start_total
            logger.info(f"TOTAL PIPELINE TIME: {total_time:.2f}s")

            # 6. Handle Actions (e.g. RECORD_FACT)
            if action_data:
                action = action_data["action"]
                payload = action_data["payload"]

                if action == "RECORD_FACT":
                    await memory_service.record_user_fact(
                        username=username,
                        concept=payload["concept"],
                        value=payload["value"],
                    )

            # 7. Unified Memory Update
            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg=text_input,
                ai_msg=ai_text,
                skill_id=skill_id,
            )

            # --- STREAM POINT 2: Yield Final Response with Audio ---
            yield VoiceResponse(
                text="",  # Text already sent
                audio_chunk=audio_b64_out,
            )
        except Exception as e:
            logger.exception("SERVICE: Fatal error in process_voice_interaction")
            yield VoiceResponse(
                text="I'm sorry, my systems are currently unresponsive."
            )

    async def process_welcome_interaction(
        self,
        session_id: str,
        username: str = "anonymous",
        skill_id: str = "aries-default",
    ):
        """
        Generates a contextual welcome message based on the current problem state.
        Bypasses full context for lower latency.
        """
        """
        Generates a contextual welcome message based on current problem state.
        """
        try:
            from app.services.aries.memory import memory_service

            context = await memory_service.get_lightweight_context(session_id)
            current_problem = context.get("current_problem")

            if current_problem:
                title = current_problem.get("title", "this problem")
                welcome_prompt = (
                    f"You are Aries. The user is currently on the 'Solve with Me' page looking at the problem '{title}'. "
                    "Briefly greet them (15 words max) and ask if they want to dive into the logic or start the Python implementation."
                )
            else:
                welcome_prompt = (
                    "You are Aries. The user is in your workspace but hasn't loaded a problem yet. "
                    "Briefly greet them (15 words max) and suggest they search for a problem or tackle today's challenge."
                )

            from app.core.config import settings

            logger.info("Generating proactive welcome message...")

            full_text = ""
            sentence_buffer = ""

            async for chunk in self.brain.generate_response_stream(
                "System: Introduce yourself to the user.",
                welcome_prompt,
                history=[],
                provider=settings.BRAIN_PROVIDER,
                model=settings.BRAIN_MODEL,
            ):
                logger.debug(f"Welcome Brain Chunk: '{chunk}'")
                full_text += chunk
                sentence_buffer += chunk

                yield VoiceResponse(text=chunk)

                if (
                    any(punct in chunk for punct in [".", "?", "!"])
                    and len(sentence_buffer) > 15
                ):
                    logger.info(
                        f"Welcome TTS triggering for sentence: '{sentence_buffer.strip()}'"
                    )
                    audio_bytes = await self.tts.speak(sentence_buffer.strip())
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    yield VoiceResponse(text="", audio_chunk=audio_b64)
                    sentence_buffer = ""

            if sentence_buffer.strip():
                audio_bytes = await self.tts.speak(sentence_buffer.strip())
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                yield VoiceResponse(text="", audio_chunk=audio_b64)

            # Record in memory
            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg="[SYSTEM_EVENT: LANDED]",
                ai_msg=full_text,
                skill_id=skill_id,
            )

        except Exception as e:
            logger.exception("Welcome interaction failed")

    def _is_noise(self, text: str) -> bool:
        if not text:
            return True
        clean_text = text.strip().lower().rstrip(".,!?")
        # Allow short common words like 'yes', 'no', 'go', 'hi'
        if len(clean_text) < 2:
            return True
        # Filter typical STT artifacts that aren't real words
        if clean_text in ["it", "it it is", "it's", "the", "a", "um"]:
            return True
        return False

    async def _build_system_prompt(
        self, skill_id: str, code_context: str, context: dict
    ) -> str:
        current_code = code_context or context.get("current_code") or ""
        current_problem = context.get("current_problem")

        # Check for user name in context
        user_name = next(
            (
                f["content"]
                for f in context.get("user_facts", [])
                if "real_name" in f["concept"]
            ),
            None,
        )

        system_prompt = self.skill_manager.get_system_prompt(skill_id, current_code)

        if not user_name:
            system_prompt += (
                "\n\nCRITICAL: You do not know the user's name yet. If they say 'Hey Aries' or introduce themselves, "
                "provide a quick overview of the app (mention coding companion, LeetCode problems, and voice search) "
                "and ask 'What should I call you?'. "
                "Once they provide a name, you MUST record it using `[RECORD_FACT: real_name | the_name]`."
            )
        else:
            system_prompt += f"\n\nYou are talking to {user_name}. Use their name occasionally, but drop it from your very first greeting of this session (the intro); keep the intro general as a coding companion overview."

        if current_problem:
            title = current_problem.get("title", "Unknown")
            system_prompt += f"\n\n- CURRENTLY LOADED PROBLEM: {title}"
            system_prompt += "\n- IMPORTANT: The user is already looking at this problem in the UI. Do NOT offer to load or search for it. Instead, help them solve it or answer questions about its logic."

            summary = context.get("problem_summary")
            if summary:
                system_prompt += f"\nProblem Summary: {summary}\n"
            else:
                import re

                desc = re.sub("<[^<]+?>", "", current_problem.get("description", ""))
                system_prompt += f"Problem Details: {desc[:500]}...\n"

        code_results = context.get("code_results")
        if code_results:
            system_prompt += "\nRecent Code Execution Results:\n"
            for res in code_results:
                status = res.get("status", "Unknown")
                system_prompt += f"- Type: {res.get('type')}, Status: {status}\n"

        semantic_knowledge = context.get("semantic_knowledge")
        if semantic_knowledge:
            system_prompt += "\n\nRelevant Knowledge Highlights:\n"
            for hit in semantic_knowledge:
                system_prompt += f"- {hit['concept']}: {hit['content']}\n"

        episodes = context.get("episodes")
        if episodes:
            system_prompt += "\n\nRecent Activity (Manual UI Actions):\n"
            for ep in episodes:
                for interaction in ep.get("interactions", []):
                    if interaction.get("role") == "system":
                        evt = interaction.get("event")
                        dtl = interaction.get("details", {})
                        system_prompt += (
                            f"- User manually triggered: {evt} (Details: {dtl})\n"
                        )

        user_facts = context.get("user_facts")
        if user_facts:
            system_prompt += "\n\nMy Memory Palace - What I know about you:\n"
            for fact in user_facts:
                system_prompt += f"- {fact['content']}\n"

        # Aries Toolbox (Tool-oriented design)
        system_prompt += "\n\n=== ARIES TOOLBOX ===\n"
        system_prompt += (
            "Your Skill defines your BEHAVIOR (persona and tutorial style). "
            "You should proactively summarize the user's progress and record it using RECORD_FACT. "
        )
        system_prompt += (
            "The following Tools define your ACTIONS and system capabilities:\n"
        )

        daily = context.get("daily_challenge")
        if daily:
            system_prompt += f"1. [LOAD_PROBLEM: {daily['slug']}] - Use this to load Today's LeetCode Challenge: {daily['title']}.\n"

        system_prompt += "2. [LOAD_PROBLEM: slug] - Use this to load any specific LeetCode problem by its slug.\n"
        system_prompt += "3. [SEARCH_PROBLEMS: query] - Use this to search for problems on LeetCode based on keywords or concepts.\n"
        system_prompt += "4. [RUN_CODE] - Use this to execute the current code in the editor with sample test cases.\n"
        system_prompt += "5. [SUBMIT_CODE] - Use this to submit the current code for official LeetCode verification.\n"
        system_prompt += "6. [NAVIGATE: view] - Use this to switch between 'home', 'problems', and 'solve' views.\n"
        system_prompt += "7. [RECORD_FACT: concept | value] - Use this to persist a fact about the user (e.g. [RECORD_FACT: weakness | recursion]). This information will be stored in your 'Memory Palace' and available in all future sessions.\n"

        system_prompt += "Note: Always confirm with the user before triggering a tool (2-step protocol).\n"
        system_prompt += "CRITICAL: To trigger a tool, you MUST use the exact syntax `[TOOL_NAME: argument]` including square brackets. These triggers will be automatically stripped from your spoken response, so you do not need to hide them or apologize for them.\n"
        system_prompt += "Aries is 'Omniscient': You are notified of every manual user action (clicks, searches, runs) via System Episodes in your context. Use this knowledge to stay in sync with the user's manual activities."

        return system_prompt


aries_service = AriesService()
