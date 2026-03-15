import json
import logging
from typing import Any

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class AriesRedisClient:
    """Async client for Redis, serving as the agent's high-speed sensory sensory state.

    AriesRedisClient manages the immediate, short-term context of a user session.
    This includes active conversation history (for windowing), current code
    editor state, and the metadata of the currently active problem. Data in
    Redis is designed for sub-millisecond access and automatically expires
    to maintain system performance.

    Attributes:
        url (str): The Redis connection URL.
        client (Optional[redis.Redis]): The underlying async Redis client instance.
    """

    def __init__(
        self,
        host: str = settings.REDIS_HOST,
        port: int = settings.REDIS_PORT,
        db: int = 0,
    ):
        """Initializes the Redis client with connection parameters.

        Args:
            host (str): Redis server hostname.
            port (int): Redis server port.
            db (int): Redis database index.
        """
        self.url = f"redis://{host}:{port}/{db}"
        self.client: redis.Redis | None = None

    async def connect(self) -> None:
        """Establishes an asynchronous connection to the Redis server."""
        if not self.client:
            self.client = redis.from_url(self.url, decode_responses=True)
            logger.info(f"REDIS: Connected to Redis at '{self.url}'")

    async def disconnect(self) -> None:
        """Gratefully closes the Redis connection."""
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("REDIS: Disconnected from Redis.")

    # --- SHORT-TERM CONTEXT (CONVERSATION WINDOW) ---

    def _get_context_key(self, session_id: str) -> str:
        """Generates the key for session conversation history."""
        return f"aries:session:{session_id}:context"

    async def add_message(
        self, session_id: str, role: str, message: str, limit: int = 15
    ) -> None:
        """Adds a message to the rolling conversation context window.

        Args:
            session_id (str): The unique session identifier.
            role (str): The message role ('user', 'aries', 'assistant').
            message (str): The raw text content of the message.
            limit (int): Max number of messages to keep in the window. Defaults to 15.
        """
        key = self._get_context_key(session_id)
        # We normalize 'aries' to 'assistant' for LLM provider consistency.
        role_label = "assistant" if role == "aries" else role
        data = json.dumps({"role": role_label, "content": message})

        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.rpush(key, data)
            await pipe.ltrim(key, -limit, -1)
            await pipe.expire(key, 3600)  # TTL of 1 hour for active sessions
            await pipe.execute()

    async def get_context(self, session_id: str) -> list[dict[str, str]]:
        """Retrieves the current rolling conversation history for a session.

        Args:
            session_id (str): The unique session identifier.

        Returns:
            List[Dict[str, str]]: A list of message dictionaries.
        """
        key = self._get_context_key(session_id)
        messages = await self.client.lrange(key, 0, -1)
        return [json.loads(m) for m in messages]

    # --- SESSION STATE MANAGEMENT ---

    def _get_state_key(self, session_id: str) -> str:
        """Generates the key for general session binary state."""
        return f"aries:session:{session_id}:state"

    async def set_state(self, session_id: str, state: str) -> None:
        """Saves a string-serialized state for the session."""
        key = self._get_state_key(session_id)
        await self.client.set(key, state, ex=3600)

    async def get_state(self, session_id: str) -> str | None:
        """Retrieves the current serialized session state."""
        key = self._get_state_key(session_id)
        return await self.client.get(key)

    # --- SENSORY STATE (CODE CONTEXT) ---

    def _get_code_key(self, session_id: str) -> str:
        """Generates the key for the active source code context."""
        return f"aries:session:{session_id}:code"

    async def set_current_code(self, session_id: str, code: str) -> None:
        """Saves the latest code snippet from the user's editor.

        Args:
            session_id (str): The unique session identifier.
            code (str): The raw source code contents.
        """
        key = self._get_code_key(session_id)
        await self.client.set(key, code, ex=3600)

    async def get_current_code(self, session_id: str) -> str | None:
        """Retrieves the most recent code snippet for the session."""
        key = self._get_code_key(session_id)
        return await self.client.get(key)

    # --- PROBLEM CONTEXT ---

    def _get_problem_key(self, session_id: str) -> str:
        """Generates the key for the active LeetCode problem metadata."""
        return f"aries:session:{session_id}:problem"

    async def set_current_problem(
        self, session_id: str, problem_data: dict[str, Any]
    ) -> None:
        """Stores the metadata of the currently viewed LeetCode problem.

        Args:
            session_id (str): The unique session identifier.
            problem_data (Dict[str, Any]): Problem dictionary (title, slug, difficulty).
        """
        key = self._get_problem_key(session_id)
        await self.client.set(key, json.dumps(problem_data), ex=3600)

    async def get_current_problem(self, session_id: str) -> dict[str, Any] | None:
        """Retrieves the problem metadata for the session."""
        key = self._get_problem_key(session_id)
        raw = await self.client.get(key)
        return json.loads(raw) if raw else None


# Global singleton instance for high-speed sensory state management.
aries_redis = AriesRedisClient()
