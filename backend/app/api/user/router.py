from fastapi import APIRouter, HTTPException, Query
from app.core.user.models import UserProfile
from app.services.user.service import user_service
from app.services.aries.memory import memory_service

router = APIRouter()


@router.get("/profile/{username}", response_model=UserProfile)
async def get_profile(username: str):
    profile = await user_service.get_profile(username)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    return profile


@router.post("/profile/sync")
async def sync_profile(profile: UserProfile, session_id: str | None = Query(None)):
    success = await user_service.sync_profile(profile)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to sync profile")

    # Unified Memory: Log Sync Event
    if session_id:
        await memory_service.record_event(
            session_id=session_id,
            username=profile.username,
            event_type="SYNC_PROFILE",
            details={"username": profile.username},
        )

    return {"status": "success"}
