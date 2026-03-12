import logging
import base64
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
        text_input: str,
        session_id: str,
        skill_id: str = "aries-default",
        code_context: str = "",
        username: str = "anonymous",
    ) -> VoiceResponse:
        try:
            # 1. Fetch Unified Context (Hot + Episodic + Semantic)
            context = await memory_service.get_full_context(
                session_id, username, text_input, skill_id
            )

            # Format Context for LLM
            history = context["history"]
            code_results = context["code_results"]
            semantic_hits = context["semantic_knowledge"]

            code_result_context = ""
            if code_results:
                code_result_context = "\nRecent Code Execution Results:\n"
                for res in code_results:
                    status = res.get("status", "Unknown")
                    c_type = res.get("type", "execution")
                    code_result_context += f"- Type: {c_type}, Status: {status}\n"
                    if status != "Accepted" and status != "Success":
                        results = res.get("results", [])
                        if isinstance(results, list) and results:
                            err = results[0].get("error") or results[0].get("stderr")
                            if err:
                                code_result_context += f"  Error: {str(err)[:200]}\n"

            semantic_context = ""
            if semantic_hits:
                semantic_context = "\nRelevant Knowledge Highlights:\n"
                for hit in semantic_hits:
                    semantic_context += f"- {hit['concept']}: {hit['content']}\n"

            # 2. Update Sensory context (Redis only for now, Mongo happens AFTER response)
            await memory_service.set_current_code(session_id, code_context)

            # 3. Generate Response
            system_prompt = self.skill_manager.get_system_prompt(skill_id, code_context)
            if code_result_context:
                system_prompt += code_result_context
            if semantic_context:
                system_prompt += semantic_context

            ai_text = await self.brain.generate_response(
                text_input, system_prompt, history=history
            )

            # 4. Generate Audio
            audio_bytes = await self.tts.speak(ai_text)
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

            # 5. Handle Actions
            action_data = self.actions.parse_action(ai_text)

            # 6. Unified Memory Update (Redis + Mongo)
            await memory_service.record_interaction(
                session_id=session_id,
                username=username,
                user_msg=text_input,
                ai_msg=ai_text,
                skill_id=skill_id,
            )

            return VoiceResponse(
                text=ai_text,
                audio_chunk=audio_b64,
                action=action_data["action"] if action_data else None,
                action_payload=action_data["payload"] if action_data else None,
            )
        except Exception as e:
            logger.exception("AriesService processing failed")
            return VoiceResponse(
                text="I'm sorry, my systems are experiencing a moment of silence."
            )


aries_service = AriesService()
