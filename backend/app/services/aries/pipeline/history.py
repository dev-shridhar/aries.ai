import logging

from langchain_community.chat_message_histories import RedisChatMessageHistory

from app.core.config import settings

logger = logging.getLogger(__name__)


class AriesHistoryManager:
    """Manages session-based conversation history using Redis and LangChain.

    This manager provides a standardized way to store and retrieve long-term
    conversation context. It integrates with Redis to ensure that history is
    persistent yet automatically expires after a period of inactivity.
    """

    @staticmethod
    def get_session_history(session_id: str) -> RedisChatMessageHistory:
        """Retrieves the persistent message history handler for a specific session.

        Args:
            session_id (str): The unique identifier for the user session.

        Returns:
            RedisChatMessageHistory: A LangChain-compatible history handler.
        """
        redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
        return RedisChatMessageHistory(
            session_id=session_id,
            url=redis_url,
            key_prefix="aries:history:",
            ttl=3600,  # 1 hour TTL for active session context
        )

    @staticmethod
    async def add_interaction(session_id: str, human_msg: str, ai_msg: str) -> None:
        """Records a single interaction turn (User -> AI) into Redis history.

        Args:
            session_id (str): The unique identifier for the user session.
            human_msg (str): The transcribed text from the user.
            ai_msg (str): The generated response from the AI.
        """
        history = AriesHistoryManager.get_session_history(session_id)
        history.add_user_message(human_msg)
        history.add_ai_message(ai_msg)
        logger.debug(f"HISTORY: Recorded interaction for session {session_id}")
