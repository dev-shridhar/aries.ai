import datetime
import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class AriesMongoClient:
    """Async client for MongoDB, serving as the agent's long-term episodic storage.

    AriesMongoClient manages persistent records that do not require high-speed
    vector retrieval. This includes conversation episodes, user profiles,
    and historical code execution results. It utilizes the Motor driver for
    efficient, non-blocking I/O.

    Attributes:
        uri (str): The MongoDB connection string.
        db_name (str): The name of the database.
        client (Optional[AsyncIOMotorClient]): The underlying Motor client instance.
        db (Optional[Any]): The active MongoDB database handle.
    """

    def __init__(
        self,
        uri: str = settings.MONGO_URI,
        database: str = settings.MONGO_DB,
    ):
        """Initializes the MongoDB client with configured connection settings.

        Args:
            uri (str): MongoDB connection URI.
            database (str): Target database name.
        """
        self.uri = uri
        self.db_name = database
        self.client: AsyncIOMotorClient | None = None
        self.db = None

    async def connect(self) -> None:
        """Establishes a connection to the MongoDB server and ensures indexes.

        This method initializes the client and sets up optimized query paths
        for episodic memory, user profiles, and code sessions.
        """
        if not self.client:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.db_name]
            logger.info(f"MONGO: Connected to MongoDB at '{self.uri}'")

            # --- INDEX OPTIMIZATION ---
            # Episodic Memory: Fast retrieval of history by user and session.
            await self.db.episodic_memory.create_index([("session_id", 1)])
            await self.db.episodic_memory.create_index([("user_id", 1)])
            await self.db.episodic_memory.create_index([("timestamp", -1)])

            # User Profiles: Unique constraints on usernames.
            await self.db.user_profiles.create_index([("username", 1)], unique=True)

            # Code Sessions: Tracking editor state transitions and executions.
            await self.db.code_sessions.create_index([("session_id", 1)])
            await self.db.code_sessions.create_index([("username", 1)])
            await self.db.code_sessions.create_index(
                [("username", 1), ("session_id", 1)]
            )
            await self.db.code_sessions.create_index([("timestamp", -1)])

            # Semantic Archive: Text-search fallback for concepts.
            await self.db.semantic_knowledge.create_index([("concept", 1)])
            await self.db.semantic_knowledge.create_index([("skill_id", 1)])
            await self.db.semantic_knowledge.create_index(
                [("concept", "text"), ("content", "text")]
            )

            # Submissions: Historical performance tracking.
            await self.db.submissions.create_index([("problem_slug", 1)])
            await self.db.submissions.create_index([("username", 1)])
            await self.db.submissions.create_index([("timestamp", -1)])

    async def disconnect(self) -> None:
        """Gratefully closes the MongoDB connection pool."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MONGO: Disconnected from MongoDB.")

    # --- USER PROFILE MANAGEMENT ---

    async def save_user_profile(self, profile: dict[str, Any]) -> Any:
        """Persists or updates the user's global profile data.

        Args:
            profile (Dict[str, Any]): The profile details (username, email, settings).

        Returns:
            Any: The MongoDB update result.
        """
        return await self.db.user_profiles.update_one(
            {"username": profile["username"]},
            {"$set": {**profile, "last_sync": datetime.datetime.utcnow()}},
            upsert=True,
        )

    async def get_user_profile(self, username: str) -> dict[str, Any] | None:
        """Retrieves a user's profile by their unique username.

        Args:
            username (str): The target username.

        Returns:
            Optional[Dict[str, Any]]: The profile document if found, else None.
        """
        return await self.db.user_profiles.find_one({"username": username})

    # --- EPISODIC MEMORY (LONG-TERM LOGGING) ---

    async def save_episode(
        self,
        session_id: str,
        user_id: Any,
        interactions: list[dict[str, Any]],
        summary: str = "",
    ) -> Any:
        """Persists a complete interaction episode (multi-turn conversation).

        Args:
            session_id (str): The unique session identifier.
            user_id (Any): The user ID (or username).
            interactions (List[Dict[str, Any]]): The sequence of turn-level data.
            summary (str): An LLM-generated summary of the interaction.

        Returns:
            Any: The MongoDB insertion result.
        """
        episode = {
            "session_id": session_id,
            "user_id": user_id,
            "interactions": interactions,
            "summary": summary,
            "timestamp": datetime.datetime.utcnow(),
            "interaction_type": "voice_tutor",
        }
        return await self.db.episodic_memory.insert_one(episode)

    async def get_recent_episodes(
        self, user_id: Any, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Fetches the most recent interaction episodes for a user.

        Args:
            user_id (Any): The identifier for the user.
            limit (int): Number of episodes to return. Defaults to 5.

        Returns:
            List[Dict[str, Any]]: A list of recent episode documents.
        """
        cursor = (
            self.db.episodic_memory.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    # --- SEMANTIC ARCHIVE (RAG FALLBACK) ---

    async def save_semantic_fact(
        self,
        concept: str,
        content: str,
        skill_id: str = "general",
        vector: list[float] | None = None,
    ) -> Any:
        """Stores a permanent fact or domain concepts in the semantic collection.

        Note: While vector search is handled by ChromaDB for speed, MongoDB
        serves as the primary source of truth (archival) for semantic data.

        Args:
            concept (str): The short concept name (e.g., 'recursion').
            content (str): The full description or fact text.
            skill_id (str): The slice identifier. Defaults to 'general'.
            vector (Optional[List[float]]): The precomputed vector embedding.

        Returns:
            Any: The MongoDB update result.
        """
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
        self, query: str, skill_id: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:
        """Performs a text-based search for facts when vector search is unavailable.

        Args:
            query (str): The search keyword or phrase.
            skill_id (Optional[str]): Limit search to a specific domain.
            limit (int): Max hits to return. Defaults to 3.

        Returns:
            List[Dict[str, Any]]: Matching fact documents.
        """
        filter_q = {}
        if skill_id:
            filter_q["skill_id"] = skill_id

        # Fallback to simple regex/text search for local development.
        filter_q["$or"] = [
            {"concept": {"$regex": query, "$options": "i"}},
            {"content": {"$regex": query, "$options": "i"}},
        ]

        cursor = self.db.semantic_knowledge.find(filter_q).limit(limit)
        return await cursor.to_list(length=limit)

    # --- CODE SESSIONS & EXECUTION CONTEXT ---

    async def save_code_session(self, session_data: dict[str, Any]) -> Any:
        """Saves a code execution or problem-solving event.

        Args:
            session_data (Dict[str, Any]): Execution details (code, language, output).

        Returns:
            Any: Insertion result.
        """
        session_data["timestamp"] = datetime.datetime.utcnow()
        return await self.db.code_sessions.insert_one(session_data)

    async def get_recent_code_sessions(
        self,
        username: str | None = None,
        session_id: str | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """Retrieves recent code activities to provide context for Aries reasoning.

        Args:
            username (Optional[str]): Sub-filter by user.
            session_id (Optional[str]): Sub-filter by session.
            limit (int): Max number of sessions.

        Returns:
            List[Dict[str, Any]]: List of recent code session documents.
        """
        query = {}
        if username:
            query["username"] = username
        if session_id:
            query["session_id"] = session_id

        cursor = self.db.code_sessions.find(query).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    # --- SUBMISSIONS (HISTORICAL RECORD) ---

    async def save_submission(self, submission: dict[str, Any]) -> Any:
        """Logs an official LeetCode submission attempt.

        Args:
            submission (Dict[str, Any]): The submission response and details.

        Returns:
            Any: Insertion result.
        """
        submission["timestamp"] = datetime.datetime.utcnow()
        return await self.db.submissions.insert_one(submission)

    async def get_submissions(
        self, problem_slug: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Fetches historical submissions for a specific problem.

        Args:
            problem_slug (str): The problem identifier.
            limit (int): Max results.

        Returns:
            List[Dict[str, Any]]: Historical records.
        """
        cursor = (
            self.db.submissions.find({"problem_slug": problem_slug})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)


# Global singleton instance for the MongoDB infrastructure.
aries_mongo = AriesMongoClient()
