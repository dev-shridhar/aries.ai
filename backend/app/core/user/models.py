"""User domain models for profile management.

This module defines the structured representation of a user's identity
and performance metrics within the platform.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Represents a standardized user profile.

    Attributes:
        username (str): Unique handle for the user (usually LeetCode/MCP slug).
        real_name (Optional[str]): The user's actual name, if provided.
        avatar (Optional[str]): URL to the user's profile image.
        ranking (int): Global or platform-specific ranking.
        last_sync (Optional[datetime]): Timestamp of the last profile synchronization.
    """

    username: str = Field(..., description="Unique platform handle.")
    real_name: str | None = Field(None, description="User's real name.")
    avatar: str | None = Field(None, description="Profile image URL.")
    ranking: int = Field(0, description="Platform ranking score.")
    preferred_language: str = Field(
        "python3", description="User's preferred coding language."
    )
    leetcode_sync_enabled: bool = Field(
        False, description="Whether LeetCode sync is active."
    )
    last_sync: datetime | None = Field(None, description="Last sync timestamp.")
