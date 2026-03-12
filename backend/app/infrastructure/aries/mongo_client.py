import logging
from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import datetime

logger = logging.getLogger(__name__)


class AriesMongoClient:
    def __init__(
        self, uri: str = "mongodb://localhost:27017", database: str = "dsa_agent"
    ):
        self.uri = uri
        self.db_name = database
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

    async def connect(self):
        if not self.client:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.db_name]
            logger.info(f"Connected to MongoDB at {self.uri}")
            # Ensure indexes
            await self.db.episodic_memory.create_index([("session_id", 1)])
            await self.db.user_profiles.create_index([("username", 1)], unique=True)
            await self.db.code_sessions.create_index([("session_id", 1)])
            await self.db.code_sessions.create_index([("username", 1)])
            await self.db.code_sessions.create_index([("timestamp", -1)])
            await self.db.semantic_knowledge.create_index([("concept", 1)])
            await self.db.semantic_knowledge.create_index([("skill_id", 1)])

    async def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    # --- User Profile ---

    async def save_user_profile(self, profile: dict):
        return await self.db.user_profiles.update_one(
            {"username": profile["username"]},
            {"$set": {**profile, "last_sync": datetime.datetime.utcnow()}},
            upsert=True,
        )

    async def get_user_profile(self, username: str) -> Optional[dict]:
        return await self.db.user_profiles.find_one({"username": username})

    # --- Episodic Memory ---

    async def save_episode(
        self, session_id: str, user_id: Any, interactions: List[dict], summary: str = ""
    ):
        """Persists a complete interaction episode."""
        episode = {
            "session_id": session_id,
            "user_id": user_id,
            "interactions": interactions,
            "summary": summary,
            "timestamp": datetime.datetime.utcnow(),
            "interaction_type": "voice_tutor",
        }
        return await self.db.episodic_memory.insert_one(episode)

    async def get_recent_episodes(self, user_id: Any, limit: int = 5) -> List[dict]:
        cursor = (
            self.db.episodic_memory.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    # --- Semantic Memory (RAG) ---

    async def save_semantic_fact(
        self,
        concept: str,
        content: str,
        skill_id: str = "general",
        vector: Optional[List[float]] = None,
    ):
        """Stores a permanent fact or skill instruction."""
        fact = {
            "concept": concept,
            "content": content,
            "skill_id": skill_id,
            "vector_embedding": vector,
            "timestamp": datetime.datetime.utcnow(),
        }
        return await self.db.semantic_knowledge.update_one(
            {"concept": concept, "skill_id": skill_id}, {"$set": fact}, upsert=True
        )

    async def query_semantic_memory(
        self, query: str, skill_id: Optional[str] = None, limit: int = 3
    ) -> List[dict]:
        """Simple text search for now, ready for Vector Search upgrade."""
        filter_q = {}
        if skill_id:
            filter_q["skill_id"] = skill_id

        # Fallback to simple regex/text search if no vector
        filter_q["$or"] = [
            {"concept": {"$regex": query, "$options": "i"}},
            {"content": {"$regex": query, "$options": "i"}},
        ]

        cursor = self.db.semantic_knowledge.find(filter_q).limit(limit)
        return await cursor.to_list(length=limit)

    # --- Code Sessions & Execution Results ---

    async def save_code_session(self, session_data: dict):
        """Saves a code execution or submission event."""
        session_data["timestamp"] = datetime.datetime.utcnow()
        return await self.db.code_sessions.insert_one(session_data)

    async def get_recent_code_sessions(
        self,
        username: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 3,
    ) -> List[dict]:
        """Fetches recent code activities to give context to Aries."""
        query = {}
        if username:
            query["username"] = username
        if session_id:
            query["session_id"] = session_id

        cursor = self.db.code_sessions.find(query).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    # --- Submissions (Historical) ---

    async def save_submission(self, submission: dict):
        submission["timestamp"] = datetime.datetime.utcnow()
        return await self.db.submissions.insert_one(submission)

    async def get_submissions(self, problem_slug: str, limit: int = 10) -> List[dict]:
        cursor = (
            self.db.submissions.find({"problem_slug": problem_slug})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)


# Global instance
aries_mongo = AriesMongoClient()
