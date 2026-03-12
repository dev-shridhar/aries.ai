import logging
from typing import Optional
from app.core.user.models import UserProfile
from app.infrastructure.aries.mongo_client import aries_mongo

logger = logging.getLogger(__name__)


class UserService:
    async def get_profile(self, username: str) -> Optional[UserProfile]:
        """Fetch user profile from MongoDB."""
        data = await aries_mongo.get_user_profile(username)
        if data:
            return UserProfile(**data)
        return None

    async def sync_profile(self, profile: UserProfile) -> bool:
        """Sync/Save user profile to MongoDB."""
        try:
            await aries_mongo.save_user_profile(profile.dict())
            return True
        except Exception as e:
            logger.error(f"Failed to sync profile for {profile.username}: {e}")
            return False


user_service = UserService()
