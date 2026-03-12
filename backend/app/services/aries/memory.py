import logging
import datetime
from typing import List, Optional, Any
from app.infrastructure.aries.redis_client import aries_redis
from app.infrastructure.aries.mongo_client import aries_mongo

logger = logging.getLogger(__name__)


class MemoryService:
    """Unified coordinator for Sensory, Short-term, Episodic, and Semantic memory."""

    async def record_interaction(
        self, session_id: str, username: str, user_msg: str, ai_msg: str, skill_id: str
    ):
        """Standard sync for a conversation turn."""
        # 1. Short-term (Redis)
        await aries_redis.add_message(session_id, "user", user_msg)
        await aries_redis.add_message(session_id, "aries", ai_msg)

        # 2. Episodic (Mongo)
        await aries_mongo.save_episode(
            session_id=session_id,
            user_id=username,
            interactions=[
                {
                    "role": "user",
                    "content": user_msg,
                    "timestamp": datetime.datetime.utcnow(),
                },
                {
                    "role": "aries",
                    "content": ai_msg,
                    "timestamp": datetime.datetime.utcnow(),
                },
            ],
            summary=f"Turn in {skill_id}",
        )

    async def record_event(
        self, session_id: str, username: str, event_type: str, details: dict
    ):
        """Captures a single system or user event (e.g. LOAD_PROBLEM)."""
        # 1. Episodic (Mongo)
        await aries_mongo.save_episode(
            session_id=session_id,
            user_id=username,
            interactions=[
                {
                    "role": "system",
                    "event": event_type,
                    "details": details,
                    "timestamp": datetime.datetime.utcnow(),
                }
            ],
            summary=f"Event: {event_type}",
        )

    async def set_current_code(self, session_id: str, code: str):
        """Sync code sensory memory."""
        await aries_redis.set_current_code(session_id, code)

    async def record_code_activity(
        self,
        session_id: str,
        username: str,
        code: str,
        activity_type: str,
        results: Any,
        status: str,
    ):
        """Sync code execution events across tiers."""
        # 1. Short-term (Redis) - Keep the latest code snippet
        await aries_redis.set_current_code(session_id, code)

        # 2. Results (Mongo)
        session_data = {
            "session_id": session_id,
            "username": username,
            "code": code,
            "type": activity_type,
            "results": results,
            "status": status,
        }
        await aries_mongo.save_code_session(session_data)

        # 3. Episodic Link (Optional - let agent know in chat history if needed)
        # We could add a system message to Redis here if we wanted immediate agent reaction

    async def get_full_context(
        self, session_id: str, username: str, query: str, skill_id: str
    ) -> dict:
        """Fetch unified context for LLM reasoning."""
        # 1. Chat History (Redis)
        history = await aries_redis.get_context(session_id)

        # 2. Recent Code Results (Mongo)
        code_results = await aries_mongo.get_recent_code_sessions(
            username, session_id, limit=2
        )

        # 3. Relevant Semantic Knowledge (Mongo)
        semantic_hits = await aries_mongo.query_semantic_memory(query, skill_id)

        return {
            "history": history,
            "code_results": code_results,
            "semantic_knowledge": semantic_hits,
        }


memory_service = MemoryService()
