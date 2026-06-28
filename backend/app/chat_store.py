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
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        logger.info("connected to redis")

    async def disconnect(self):
        if self.client:
            await self.client.close()

    async def add_turn(self, session: str, role: str, text: str, limit: int = 10):
        key = f"chat:{session}"
        data = json.dumps({"role": role, "content": text})
        async with self.client.pipeline(transaction=True) as pipe:
            await pipe.rpush(key, data)
            await pipe.ltrim(key, -limit, -1)
            await pipe.expire(key, 3600)
            await pipe.execute()

    async def get_history(self, session: str) -> list[dict]:
        key = f"chat:{session}"
        raw = await self.client.lrange(key, 0, -1)
        return [json.loads(m) for m in raw]

    async def set_code(self, session: str, code: str):
        await self.client.set(f"code:{session}", code, ex=3600)

    async def get_code(self, session: str) -> Optional[str]:
        return await self.client.get(f"code:{session}")

    async def set_problem(self, session: str, problem: dict):
        await self.client.set(f"problem:{session}", json.dumps(problem), ex=3600)

    async def get_problem(self, session: str) -> Optional[dict]:
        raw = await self.client.get(f"problem:{session}")
        return json.loads(raw) if raw else None


chat_store = ChatStore()
