"""Unit tests for the UserService.

These tests verify the retrieval and synchronization of user profiles,
ensuring proper interaction with the MongoDB infrastructure layer
using asynchronous mocks.
"""

from unittest.mock import AsyncMock, patch

import pytest
from app.core.user.models import UserProfile
from app.services.user.service import user_service


@pytest.mark.asyncio
async def test_get_profile_success():
    """Verify that a valid profile is correctly retrieved and parsed."""
    mock_data = {
        "username": "testuser",
        "leetcode_sync_enabled": True,
        "preferred_language": "python3",
    }

    with patch(
        "app.services.user.service.aries_mongo.get_user_profile", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = mock_data

        profile = await user_service.get_profile("testuser")

        assert profile is not None
        assert profile.username == "testuser"
        assert profile.leetcode_sync_enabled is True
        mock_get.assert_called_once_with("testuser")


@pytest.mark.asyncio
async def test_get_profile_not_found():
    """Verify that None is returned if the user profile does not exist."""
    with patch(
        "app.services.user.service.aries_mongo.get_user_profile", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None

        profile = await user_service.get_profile("nonexistent")
        assert profile is None


@pytest.mark.asyncio
async def test_get_profile_error():
    """Verify that None is returned and error logged if DB fetch fails."""
    with patch(
        "app.services.user.service.aries_mongo.get_user_profile",
        side_effect=Exception("DB Error"),
    ):
        profile = await user_service.get_profile("test_error")
        assert profile is None


@pytest.mark.asyncio
async def test_sync_profile_success():
    """Verify that a profile is correctly synchronized to the database."""
    profile = UserProfile(username="testuser", preferred_language="javascript")

    with patch(
        "app.services.user.service.aries_mongo.save_user_profile",
        new_callable=AsyncMock,
    ) as mock_save:
        mock_save.return_value = None

        success = await user_service.sync_profile(profile)

        assert success is True
        mock_save.assert_called_once()
        # Verify dumped data contains the username
        args, _ = mock_save.call_args
        assert args[0]["username"] == "testuser"


@pytest.mark.asyncio
async def test_sync_profile_error():
    """Verify that False is returned and error logged if DB save fails."""
    profile = UserProfile(username="test_error", preferred_language="python")
    with patch(
        "app.services.user.service.aries_mongo.save_user_profile",
        side_effect=Exception("Save Error"),
    ):
        success = await user_service.sync_profile(profile)
        assert success is False
