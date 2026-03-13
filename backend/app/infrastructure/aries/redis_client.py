import json
import logging
from typing import List, Optional
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class AriesRedisClient:
    def __init__(
        self,
        host: str = settings.REDIS_HOST,
        port: int = settings.REDIS_PORT,
        db: int = 0,
    ):
        self.url = f"redis://{host}:{port}/{db}"
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        if not self.client:
            self.client = redis.from_url(self.url, decode_responses=True)
            logger.info(f"Connected to Redis at {self.url}")

    async def disconnect(self):
        if self.client:
            await self.client.close()
            self.client = None

    # --- Short-term Memory (Context) ---

    def _get_context_key(self, session_id: str) -> str:
        return f"aries:session:{session_id}:context"

    async def add_message(
        self, session_id: str, role: str, message: str, limit: int = 15
    ):
        """Adds a message to the rolling context window."""
        key = self._get_context_key(session_id)
        data = json.dumps({"role": role, "content": message})

        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.rpush(key, data)
            await pipe.ltrim(key, -limit, -1)
            await pipe.expire(key, 3600)  # TTL 1 hour
            await pipe.execute()

    async def get_context(self, session_id: str) -> List[dict]:
        """Retrieves the current session context."""
        key = self._get_context_key(session_id)
        messages = await self.client.lrange(key, 0, -1)
        # Map 'aries' -> 'assistant' for LLM compatibility
        history = []
        for m in messages:
            msg = json.loads(m)
            if msg.get("role") == "aries":
                msg["role"] = "assistant"
            history.append(msg)
        return history

    # --- State Management ---

    def _get_state_key(self, session_id: str) -> str:
        return f"aries:session:{session_id}:state"

    async def set_state(self, session_id: str, state: str):
        key = self._get_state_key(session_id)
        await self.client.set(key, state, ex=3600)

    async def get_state(self, session_id: str) -> Optional[str]:
        key = self._get_state_key(session_id)
        return await self.client.get(key)

    # --- Code Context ---
    def _get_code_key(self, session_id: str) -> str:
        return f"aries:session:{session_id}:code"

    async def set_current_code(self, session_id: str, code: str):
        key = self._get_code_key(session_id)
        await self.client.set(key, code, ex=3600)

    async def get_current_code(self, session_id: str) -> Optional[str]:
        key = self._get_code_key(session_id)
        return await self.client.get(key)

    # --- Problem Context ---
    def _get_problem_key(self, session_id: str) -> str:
        return f"aries:session:{session_id}:problem"

    async def set_current_problem(self, session_id: str, problem_data: dict):
        key = self._get_problem_key(session_id)
        await self.client.set(key, json.dumps(problem_data), ex=3600)

    async def get_current_problem(self, session_id: str) -> Optional[dict]:
        key = self._get_problem_key(session_id)
        raw = await self.client.get(key)
        return json.loads(raw) if raw else None


# Global instances can be initialized in app lifetime
aries_redis = AriesRedisClient()
