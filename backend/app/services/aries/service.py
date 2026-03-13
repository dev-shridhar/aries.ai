import logging
import base64
import json
import asyncio
from app.services.aries.memory import memory_service
from app.services.aries.pipeline.stt import stt_adapter
from app.services.aries.pipeline.tts import tts_adapter
from app.services.aries.pipeline.brain import brain_adapter
from app.services.aries.skills.manager import skill_manager
from app.services.aries.actions.triggers import action_trigger
from app.core.aries.models import VoiceResponse

logger = logging.getLogger(__name__)


class AriesService:
    def __init__(self):
        self.skill_manager = skill_manager
        self.brain = brain_adapter
        self.stt = stt_adapter
        self.tts = tts_adapter
        self.actions = action_trigger

    async def process_voice_interaction(
        self,
        audio_b64: str,
        session_id: str,
        skill_id: str = "aries-default",
        code_context: str = "",
        username: str = "anonymous",
    ) -> VoiceResponse:
        try:
            # 1. Decode Audio and Transcribe
            if not audio_b64:
                return VoiceResponse(text="I'm listening, but I didn't hear anything.")

            logger.info(f"Processing audio chunk for session {session_id}")
            audio_bytes = base64.b64decode(audio_b64)

            # STT Event
            text_input = await self.stt.transcribe(audio_bytes)
            logger.info(f"STT Transcript: '{text_input}'")

            # 1.5 Noise Filtering for Silence
            # Some STT models return "It" or "..." or "It it is." for background noise
            is_noise = False
            if text_input:
                clean_text = text_input.strip().lower().rstrip(".")
                if len(clean_text) < 3 or clean_text in [
                    "it",
                    "it it is",
                    "it's",
                    "yes",
                    "i",
                ]:
                    # These common mis-transcriptions of silence should be treated as empty
                    is_noise = True

            if not text_input or text_input.strip() == "" or is_noise:
                logger.info(
                    "Empty or noise transcript detected, returning proactive silence prompt with audio."
                )
                txt = "Hey, are you trying to talk? I cannot hear you."
                audio_bytes_out = await self.tts.speak(txt)
                audio_b64_out = base64.b64encode(audio_bytes_out).decode("utf-8")
                return VoiceResponse(text=txt, audio_chunk=audio_b64_out)
            # 2. Fetch Unified Context (Hot + Episodic + Semantic)
            context = await memory_service.get_full_context(
                session_id, username, text_input, skill_id
            )

            # 3. Format Context for LLM
            system_prompt = await self._build_system_prompt(
                skill_id, code_context, context
            )

            # 3.5 Update Sensory context (Code)
            if code_context:
                await memory_service.set_current_code(session_id, code_context)

            from app.core.config import settings

            logger.info(
                f"Querying High-speed Brain ({settings.BRAIN_PROVIDER} {settings.BRAIN_MODEL}) with transcript: '{text_input}'"
            )
            ai_text = await self.brain.generate_response(
                text_input,
                system_prompt,
                history=context["history"],
                provider=settings.BRAIN_PROVIDER,
                model=settings.BRAIN_MODEL,
            )
            logger.info(f"Brain Response: '{ai_text}'")

            # 5. Generate Audio (TTS Event)
            logger.info("Generating Speech via TTS...")
            audio_bytes_out = await self.tts.speak(ai_text)
            audio_b64_out = base64.b64encode(audio_bytes_out).decode("utf-8")
            logger.info("TTS Generation Complete.")

            # 6. Handle Actions
            action_data = self.actions.parse_action(ai_text)

            # 7. Unified Memory Update (Redis + Mongo)
            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg=text_input,
                ai_msg=ai_text,
                skill_id=skill_id,
            )

            return VoiceResponse(
                text=ai_text,
                audio_chunk=audio_b64_out,
                action=action_data["action"] if action_data else None,
                action_payload=action_data["payload"] if action_data else None,
            )
        except Exception as e:
            logger.exception("AriesService processing failed")
            return VoiceResponse(
                text="I'm sorry, my systems are experiencing a moment of silence."
            )

    async def process_welcome_interaction(
        self,
        session_id: str,
        username: str = "anonymous",
        skill_id: str = "aries-default",
    ):
        """
        Generates an enthusiastic welcome message and streams it.
        """
        try:
            # 1. Fetch Daily Challenge Info for extra flair
            daily_title = "today's challenge"
            try:
                from app.api.mcp.router import mcp_service  # Reuse logic or import

                async with mcp_service.get_session() as (session, _):
                    raw = await mcp_service.call_tool(
                        session, "get_daily_challenge", {}
                    )
                    data = json.loads(raw)
                    problem = data.get("problem", data)
                    question = (
                        (problem.get("question") or problem)
                        if isinstance(problem, dict)
                        else {}
                    )
                    if isinstance(question, dict):
                        daily_title = question.get("title", "today's challenge")
            except Exception as e:
                logger.warning(f"Could not fetch daily challenge for welcome: {e}")

            # 2. Specialized Welcome Prompt (Concise: 15-20 words)
            welcome_prompt = (
                "You are Aries, a high-performance DSA AI tutor. The user has just landed. "
                "Enthusiastically welcome them in exactly one short sentence (max 15 words). "
                f"Mention today's challenge: {daily_title}."
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

    async def process_streaming_interaction(
        self,
        text_input: str,
        session_id: str,
        skill_id: str = "aries-default",
        code_context: str = "",
        username: str = "anonymous",
    ):
        """
        Handles a confirmed transcript by streaming LLM response and TTS.
        """
        try:
            # 1. Noise Filtering (consistency with batch)
            if self._is_noise(text_input):
                logger.info(
                    "Noise detected in stream transcript, skipping brain trigger."
                )
                return

            # 2. Fetch Context
            context = await memory_service.get_full_context(
                session_id, username, text_input, skill_id
            )

            # 3. Format Context
            system_prompt = await self._build_system_prompt(
                skill_id, code_context, context
            )

            if code_context:
                await memory_service.set_current_code(session_id, code_context)

            from app.core.config import settings

            logger.info(
                f"Streaming Brain ({settings.BRAIN_MODEL}) for transcript: '{text_input}'"
            )

            # Special case: Wake word detection without further content
            is_wake_only = text_input.lower().strip() in ["hey aries", "aries"]
            user_name = next(
                (
                    f["content"]
                    for f in context.get("user_facts", [])
                    if "real_name" in f["concept"]
                ),
                None,
            )

            if is_wake_only:
                if not user_name:
                    system_prompt = (
                        "You are Aries. The user just woke you up with 'Hey Aries'. "
                        "Provide a ultra-concise overview (5-10 words) of your mission as a DSA AI tutor. "
                        "Then ask 'What should I call you?'. "
                        "BE EXTREMELY BRIEF AND STOP THERE."
                    )
                else:
                    system_prompt = f"You are Aries. {user_name} just woke you up with 'Hey Aries'. Briefly (under 10 words) ask how you can help them today."
                logger.info(
                    f"Wake word only detected. Forcing brief response for {'unknown' if not user_name else 'known'} user."
                )

            full_text = ""
            sentence_buffer = ""

            async for chunk in self.brain.generate_response_stream(
                text_input,
                system_prompt,
                history=context["history"],
                provider=settings.BRAIN_PROVIDER,
                model=settings.BRAIN_MODEL,
            ):
                full_text += chunk
                sentence_buffer += chunk

                # Yield text chunk immediately
                yield VoiceResponse(text=chunk)

                # If sentence complete, generate and yield audio
                # Using a slightly more robust regex or set of punctuation
                if (
                    any(punct in chunk for punct in [".", "?", "!"])
                    and len(sentence_buffer) > 15
                ):
                    logger.info("Generating audio for sentence chunk...")
                    audio_bytes = await self.tts.speak(sentence_buffer.strip())
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    yield VoiceResponse(text="", audio_chunk=audio_b64)
                    sentence_buffer = ""

            # Final check for any remaining buffer
            if sentence_buffer.strip():
                audio_bytes = await self.tts.speak(sentence_buffer.strip())
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                yield VoiceResponse(text="", audio_chunk=audio_b64)

            # Handle Actions and Memory
            action_data = self.actions.parse_action(full_text)
            if action_data:
                action = action_data["action"]
                payload = action_data["payload"]

                if action == "RECORD_FACT":
                    await memory_service.record_user_fact(
                        username=username,
                        concept=payload["concept"],
                        value=payload["value"],
                    )

                yield VoiceResponse(
                    text="",
                    action=action,
                    action_payload=payload,
                )

            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg=text_input,
                ai_msg=full_text,
                skill_id=skill_id,
            )

        except Exception as e:
            logger.exception("Streaming interaction failed")
            yield VoiceResponse(text="I'm sorry, I hit a snag while processing that.")

    def _is_noise(self, text: str) -> bool:
        if not text:
            return True
        clean_text = text.strip().lower().rstrip(".")
        if len(clean_text) < 3 or clean_text in ["it", "it it is", "it's", "yes", "i"]:
            return True
        return False

    async def _build_system_prompt(
        self, skill_id: str, code_context: str, context: dict
    ) -> str:
        current_code = code_context or context.get("current_code") or ""
        current_problem = context.get("current_problem")
        
        # Check for user name in context
        user_name = next((f["content"] for f in context.get("user_facts", []) if "real_name" in f["concept"]), None)

        system_prompt = self.skill_manager.get_system_prompt(skill_id, current_code)

        if not user_name:
            system_prompt += (
                "\n\nCRITICAL: You do not know the user's name yet. If they say 'Hey Aries' or introduce themselves, "
                "give a 5-10 word overview of your mission as a DSA AI tutor and ask 'What should I call you?'. "
                "Once they provide a name, you MUST record it using `[RECORD_FACT: real_name | the_name]`."
            )
        else:
            system_prompt += f"\n\nYou are talking to {user_name}. Use their name occasionally."

        if current_problem:
            title = current_problem.get("title", "Unknown")
            summary = context.get("problem_summary")
            system_prompt += f"\n\nCurrent Problem: {title}\n"
            if summary:
                system_prompt += f"Problem Summary: {summary}\n"
            else:
                import re

                desc = re.sub("<[^<]+?>", "", current_problem.get("description", ""))
                system_prompt += f"Problem Details: {desc[:500]}...\n"

        if code_results:
            system_prompt += "\nRecent Code Execution Results:\n"
            for res in code_results:
                status = res.get("status", "Unknown")
                system_prompt += f"- Type: {res.get('type')}, Status: {status}\n"

        if semantic_hits:
            system_prompt += "\n\nRelevant Knowledge Highlights:\n"
            for hit in semantic_hits:
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
