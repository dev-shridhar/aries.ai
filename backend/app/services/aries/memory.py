import logging
import datetime
import json
import asyncio
from typing import List, Optional, Any
from app.infrastructure.aries.redis_client import aries_redis
from app.infrastructure.aries.mongo_client import aries_mongo

logger = logging.getLogger(__name__)


class MemoryService:
    """Unified coordinator for Sensory, Short-term, Episodic, and Semantic memory."""

    async def record_user_fact(self, username: str, concept: str, value: str):
        """Persists a fact about the user in the 'Memory Palace'."""
        from app.services.aries.pipeline.brain import brain_adapter
        from app.core.config import settings

        # Generate embedding for the fact
        vector = await brain_adapter.get_embedding(
            f"{concept}: {value}", model=settings.EMBEDDING_MODEL
        )

        fact_key = f"user_fact:{username}:{concept}"
        await aries_mongo.save_semantic_fact(
            concept=fact_key,
            content=value,
            skill_id="user-personality",
            vector=vector
        )
        logger.info(f"Recorded embedded fact for {username}: {concept} = {value}")

    async def summarize_and_store_problem(
        self, slug: str, title: str, description: str
    ):
        """Asynchronously summarizes a problem and stores it in semantic memory."""
        from app.services.aries.pipeline.brain import brain_adapter
        from app.core.config import settings

        system_prompt = "You are a DSA expert. Summarize the following coding problem into 2-3 concise sentences. Focus on the core objective and constraints."
        user_msg = f"Problem: {title}\n\n{description}"

        # 1. Summarization with Configured Brain
        summary = await brain_adapter.generate_response(
            user_msg,
            system_prompt,
            provider=settings.BRAIN_PROVIDER,
            model=settings.BRAIN_MODEL,
        )

        # 2. Embedding with Configured Model
        vector = await brain_adapter.get_embedding(
            description, model=settings.EMBEDDING_MODEL
        )

        # 3. Store in Semantic Memory
        await aries_mongo.save_semantic_fact(
            concept=f"problem_summary:{slug}",
            content=summary,
            skill_id="aries-default",
            vector=vector,
        )
        logger.info(
            f"Summarized and indexed problem: {slug} using {settings.BRAIN_PROVIDER}/{settings.BRAIN_MODEL}"
        )

    async def record_interaction(
        self, session_id: str, username: str, user_msg: str, ai_msg: str, skill_id: str
    ):
        """Standard sync for a conversation turn."""
        # 1. Short-term (Redis)
        await aries_redis.add_message(session_id, "user", user_msg)
        await aries_redis.add_message(session_id, "assistant", ai_msg)

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

    async def set_current_problem(self, session_id: str, problem_data: dict):
        """Sync problem context sensory memory."""
        await aries_redis.set_current_problem(session_id, problem_data)

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

    async def get_lightweight_context(self, session_id: str) -> dict:
        """Fetch only the most critical hot context from Redis (no Mongo/MCP)."""
        history = await aries_redis.get_context(session_id)
        current_problem = await aries_redis.get_current_problem(session_id)
        return {
            "history": history,
            "current_problem": current_problem,
        }

    async def get_full_context(
        self, session_id: str, username: str, query: str = "", skill_id: str = "aries-default"
    ) -> dict:
        """Fetch unified context for LLM reasoning."""
        # 1. Hot Context (Redis)
        history = await aries_redis.get_context(session_id)
        current_code = await aries_redis.get_current_code(session_id)
        current_problem = await aries_redis.get_current_problem(session_id)

        # 2. Episodic (Mongo) - Recent Code Results
        code_results = await aries_mongo.get_recent_code_sessions(
            username, session_id, limit=2
        )

        # 3. Episodic (Mongo) - Recent Interaction/System Episodes
        episodes = await aries_mongo.get_recent_episodes(username, limit=3)

        # 4. Semantic (Mongo) - Persistent User Facts (Memory Palace)
        # Prefix search for explicit facts + semantic search for relatedness
        direct_facts = await aries_mongo.query_semantic_memory(
            f"user_fact:{username}:", skill_id="user-personality", limit=10
        )
        
        # Hybrid Semantic Check for facts
        semantic_facts = []
        if query and len(query) > 5:
            from app.services.aries.pipeline.brain import brain_adapter
            from app.core.config import settings
            query_vector = await brain_adapter.get_embedding(query, model=settings.EMBEDDING_MODEL)
            semantic_facts = await aries_mongo.semantic_search(
                vector=query_vector, skill_id="user-personality", limit=3
            )

        # Merge and dedup facts
        all_facts = {f["concept"]: f for f in direct_facts}
        for f in semantic_facts:
            all_facts[f["concept"]] = f
        
        user_facts = list(all_facts.values())

        # 5. Semantic (Mongo) - Relevant Knowledge
        semantic_hits = await aries_mongo.query_semantic_memory(query, skill_id)

        # 4. Hybrid Logic: If we have a problem, ensure the summary is fetched
        problem_summary = None
        if current_problem and current_problem.get("slug"):
            slug = current_problem["slug"]
            summaries = await aries_mongo.query_semantic_memory(
                f"problem_summary:{slug}", skill_id
            )
            if summaries:
                problem_summary = summaries[0]["content"]

        # 5. Daily Challenge (Inject for proactive mapping)
        daily_challenge = None
        try:
            from app.api.mcp.router import daily_challenge_cache
            if daily_challenge_cache:
                daily_challenge = daily_challenge_cache.get("data")
            else:
                # If no cache, try to fetch once but don't block heavily
                from app.api.mcp.router import mcp_service
                async with mcp_service.get_session() as (session, _):
                    raw = await mcp_service.call_tool(session, "get_daily_challenge", {})
                    data = json.loads(raw)
                    problem = data.get("problem", data)
                    question = (problem.get("question") or problem) if isinstance(problem, dict) else {}
                    if isinstance(question, dict):
                        daily_challenge = {
                            "slug": question.get("titleSlug"),
                            "title": question.get("title")
                        }
        except Exception as e:
            logger.debug(f"Daily challenge fetch failed: {e}")
            pass

        return {
            "history": history,
            "current_code": current_code,
            "current_problem": current_problem,
            "problem_summary": problem_summary,
            "code_results": code_results,
            "semantic_knowledge": semantic_hits,
            "daily_challenge": daily_challenge,
            "episodes": episodes,
            "user_facts": user_facts,
        }


memory_service = MemoryService()
