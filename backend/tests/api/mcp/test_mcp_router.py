"""Unit tests for the MCP API router."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@asynccontextmanager
async def mock_mcp_session_factory(session=None, tools=None):
    """Factory for creating mock MCP sessions for testing."""
    yield session or MagicMock(), tools or []


@pytest.mark.asyncio
async def test_get_daily_endpoint():
    """Verify that the /daily endpoint correctly fetches challenge metadata."""
    mock_session = MagicMock()
    # Mock the tool call to return expected JSON
    mock_payload = {
        "problem": {"titleSlug": "test-slug", "title": "Test Problem"},
        "date": "2024-03-15",
    }

    with patch("app.api.mcp.router.mcp_service.get_session") as mock_get_session:
        # get_session returns the async context manager
        mock_get_session.return_value = mock_mcp_session_factory(mock_session)

        with patch(
            "app.api.mcp.router.mcp_service.call_tool", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = json.dumps(mock_payload)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/daily")

            assert response.status_code == 200
            data = response.json()
            assert data["slug"] == "test-slug"
            assert data["title"] == "Test Problem"


@pytest.mark.asyncio
async def test_get_problem_endpoint():
    """Verify that the /problem/{slug} endpoint fetches high-fidelity metadata."""
    mock_session = MagicMock()
    mock_payload = {
        "problem": {
            "title": "Two Sum",
            "content": "Description",
            "codeSnippets": [{"langSlug": "python3", "code": "class Solution:"}],
        }
    }

    with patch("app.api.mcp.router.mcp_service.get_session") as mock_get_session:
        mock_get_session.return_value = mock_mcp_session_factory(mock_session)

        with patch(
            "app.api.mcp.router.mcp_service.call_tool", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = json.dumps(mock_payload)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/problem/two-sum")

            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Two Sum"
            assert "pythonStub" in data


@pytest.mark.asyncio
async def test_search_problems_endpoint():
    """Verify that the /search endpoint performs keyword-based discovery."""
    mock_session = MagicMock()
    mock_payload = {
        "problems": {"questions": [{"titleSlug": "slug", "title": "Title"}]}
    }

    with patch("app.api.mcp.router.mcp_service.get_session") as mock_get_session:
        mock_get_session.return_value = mock_mcp_session_factory(mock_session)

        with patch(
            "app.api.mcp.router.mcp_service.call_tool", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = json.dumps(mock_payload)

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                response = await ac.get("/api/search?q=linked+list")

            assert response.status_code == 200
            data = response.json()
            assert "problems" in data
            assert len(data["problems"]) == 1
