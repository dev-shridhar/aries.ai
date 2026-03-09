from abc import ABC, abstractmethod
from typing import Any

class BaseAgent(ABC):
    """
    Base class for all AI agents in the system.
    Enforces a standard interface for handling user input and maintaining context.
    """

    @abstractmethod
    async def process_message(self, user_input: str, session_id: str | None = None, user_context: str | None = None) -> str:
        """
        Process a message from the user and return the agent's response.
        :param user_input: The text input from the user.
        :param session_id: Optional ID for conversation logging and history.
        :param user_context: Optional context (like current problem being viewed).
        :return: The string response from the agent.
        """
        pass
