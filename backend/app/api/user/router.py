"""API router for the User feature slice.

This module exposes endpoints for retrieving user profiles and
synchronizing platform-wide user data with the persistence layer.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.core.user.models import UserProfile
from app.services.aries.memory import memory_service
from app.services.user.service import user_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/profile/{username}", response_model=UserProfile)
async def get_profile(username: str) -> UserProfile:
    """Retrieves a user's profile metadata.

    Args:
        username (str): The unique platform handle of the user.

    Returns:
        UserProfile: The populated user profile object.

    Raises:
        HTTPException: 404 if the profile does not exist.
    """
    profile = await user_service.get_profile(username)
    if not profile:
        raise HTTPException(
            status_code=404, detail=f"Profile for '{username}' not found."
        )
    return profile


@router.post("/profile/sync")
async def sync_profile(
    profile: UserProfile, session_id: str | None = Query(None)
) -> dict[str, str]:
    """Synchronizes a user profile and logs the event to unified memory.

    Args:
        profile (UserProfile): The profile data to sync.
        session_id (Optional[str]): Current active session for memory logging.

    Returns:
        Dict[str, str]: Status of the synchronization operation.

    Raises:
        HTTPException: 500 if the persistence operation fails.
    """
    success = await user_service.sync_profile(profile)
    if not success:
        raise HTTPException(status_code=500, detail="Database synchronization failed.")

    # Unified Memory: Log Sync Event for autonomous context retrieval
    if session_id:
        await memory_service.record_event(
            session_id=session_id,
            username=profile.username,
            event_type="SYNC_PROFILE",
            details={"username": profile.username},
        )

    return {"status": "success"}
