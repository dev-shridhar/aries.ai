import json
import logging
from typing import Optional
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)


class ChatStore:
    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        try:
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.client.ping()
            logger.info("connected to redis")
        except Exception as e:
            logger.warning(f"redis unavailable: {e}")
            self.client = None

    async def disconnect(self):
        if self.client:
            await self.client.close()

    async def add_turn(self, session: str, role: str, text: str, limit: int = 10):
        if not self.client:
            return
        key = f"chat:{session}"
        data = json.dumps({"role": role, "content": text})
        try:
            async with self.client.pipeline(transaction=True) as pipe:
                await pipe.rpush(key, data)
                await pipe.ltrim(key, -limit, -1)
                await pipe.expire(key, 3600)
                await pipe.execute()
        except Exception as e:
            logger.warning(f"redis add_turn failed: {e}")

    async def get_history(self, session: str) -> list[dict]:
        if not self.client:
            return []
        key = f"chat:{session}"
        try:
            raw = await self.client.lrange(key, 0, -1)
            return [json.loads(m) for m in raw]
        except Exception as e:
            logger.warning(f"redis get_history failed: {e}")
            return []

    async def set_code(self, session: str, code: str):
        if not self.client:
            return
        try:
            await self.client.set(f"code:{session}", code, ex=3600)
        except Exception as e:
            logger.warning(f"redis set_code failed: {e}")

    async def get_code(self, session: str) -> Optional[str]:
        if not self.client:
            return None
        try:
            return await self.client.get(f"code:{session}")
        except Exception as e:
            logger.warning(f"redis get_code failed: {e}")
            return None

    async def set_problem(self, session: str, problem: dict):
        if not self.client:
            return
        try:
            await self.client.set(f"problem:{session}", json.dumps(problem), ex=3600)
        except Exception as e:
            logger.warning(f"redis set_problem failed: {e}")

    async def get_problem(self, session: str) -> Optional[dict]:
        if not self.client:
            return None
        try:
            raw = await self.client.get(f"problem:{session}")
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning(f"redis get_problem failed: {e}")
            return None


chat_store = ChatStore()
