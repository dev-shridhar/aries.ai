"""Unit tests for the User API router.

These tests verify the profile retrieval and synchronization endpoints,
ensuring proper service orchestration and error handling using
asynchronous testing patterns.
"""

from unittest.mock import AsyncMock, patch

import pytest
from app.core.user.models import UserProfile
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_get_profile_endpoint():
    """Verify that the GET /profile/{username} endpoint returns existing profiles."""
    mock_profile = UserProfile(username="testuser", preferred_language="python3")

    # Patch the singleton instance in the router module
    with patch(
        "app.api.user.router.user_service.get_profile", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = mock_profile

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # Corrected path: /api/profile/{username}
            response = await ac.get("/api/profile/testuser")

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        mock_get.assert_called_once_with("testuser")


@pytest.mark.asyncio
async def test_get_profile_not_found_endpoint():
    """Verify that the GET /profile/{username} endpoint returns 404 for missing users."""
    with patch(
        "app.api.user.router.user_service.get_profile", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/profile/ghost")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sync_profile_endpoint():
    """Verify that the POST /profile/sync endpoint correctly updates user data."""
    with patch(
        "app.api.user.router.user_service.sync_profile", new_callable=AsyncMock
    ) as mock_sync:
        mock_sync.return_value = True

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            payload = {
                "username": "testuser",
                "preferred_language": "cplusplus",
                "leetcode_sync_enabled": True,
            }
            # Corrected path: /api/profile/sync
            response = await ac.post("/api/profile/sync", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_sync.assert_called_once()
