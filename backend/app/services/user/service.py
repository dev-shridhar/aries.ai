"""Domain service for user profile management and persistence.

This module provides high-level operations for retrieving and
synchronizing user profiles across the persistence layer (MongoDB).
"""

import logging

from app.core.user.models import UserProfile
from app.infrastructure.aries.mongo_client import aries_mongo

logger = logging.getLogger(__name__)


class UserService:
    """Manages User Profiles and persistence lifecycle.

    This service acts as the bridge between the domain model (UserProfile)
    and the infrastructure layer (aries_mongo).
    """

    async def get_profile(self, username: str) -> UserProfile | None:
        """Fetches a user profile from the infrastructure layer.

        Args:
            username (str): The unique handle of the user to retrieve.

        Returns:
            Optional[UserProfile]: The populated profile object if found,
                else None.
        """
        try:
            data = await aries_mongo.get_user_profile(username)
            if data:
                return UserProfile(**data)
            return None
        except Exception as e:
            logger.error(f"USER_SERVICE: Failed to fetch profile for '{username}': {e}")
            return None

    async def sync_profile(self, profile: UserProfile) -> bool:
        """Synchronizes/Saves a user profile to the persistence layer.

        Args:
            profile (UserProfile): The validated profile object to save.

        Returns:
            bool: True if synchronization was successful, False otherwise.
        """
        try:
            # We use model_dump() for modern Pydantic v2 compatibility
            await aries_mongo.save_user_profile(profile.model_dump())
            return True
        except Exception as e:
            logger.error(f"USER_SERVICE: Sync failure for '{profile.username}': {e}")
            return False


# Singleton instance for global access
user_service = UserService()
