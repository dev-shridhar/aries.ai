"""Unit tests for the AriesTools toolbox.

These tests verify the sensory and retrieval tools used by the Aries agent,
including Redis-based history/state retrieval and Chroma-based
semantic search, with coverage for both success and error paths.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.aries.pipeline.tools import AriesTools


@pytest.mark.asyncio
async def test_get_recent_history_success():
    """Verify history retrieval from Redis."""
    mock_history = [{"role": "user", "content": "hello"}]
    with patch(
        "app.services.aries.pipeline.tools.aries_redis", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get_context.return_value = mock_history
        result = await AriesTools.get_recent_history.ainvoke(
            {"session_id": "s1", "limit": 1}
        )
        assert "USER: hello" in result


@pytest.mark.asyncio
async def test_get_recent_history_error():
    """Verify error isolation when Redis history fetch fails."""
    with patch(
        "app.services.aries.pipeline.tools.aries_redis", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get_context.side_effect = Exception("Redis error")
        result = await AriesTools.get_recent_history.ainvoke({"session_id": "s1"})
        assert "Error retrieving history" in result


@pytest.mark.asyncio
async def test_get_current_state_success():
    """Verify state retrieval (code + problem) from Redis."""
    with patch(
        "app.services.aries.pipeline.tools.aries_redis", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get_current_code.return_value = "print(1)"
        mock_redis.get_current_problem.return_value = {"title": "Two Sum"}
        result = await AriesTools.get_current_state.ainvoke({"session_id": "s1"})
        assert "print(1)" in result
        assert "Two Sum" in result


@pytest.mark.asyncio
async def test_get_current_state_empty():
    """Verify state representation when editor/problem are empty."""
    with patch(
        "app.services.aries.pipeline.tools.aries_redis", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get_current_code.return_value = None
        mock_redis.get_current_problem.return_value = None
        result = await AriesTools.get_current_state.ainvoke({"session_id": "s1"})
        assert "Editor is empty" in result
        assert "No problem currently loaded" in result


@pytest.mark.asyncio
async def test_get_current_state_error():
    """Verify error isolation when Redis state fetch fails."""
    with patch(
        "app.services.aries.pipeline.tools.aries_redis", new_callable=AsyncMock
    ) as mock_redis:
        mock_redis.get_current_code.side_effect = Exception("Failure")
        result = await AriesTools.get_current_state.ainvoke({"session_id": "s1"})
        assert "Error retrieving state" in result


@pytest.mark.asyncio
async def test_search_memory_palace_success():
    """Verify semantic memory search in ChromaDB."""
    mock_results = [{"content": "Blue", "metadata": {"concept": "color"}}]
    with patch(
        "app.services.aries.pipeline.tools.chroma_manager", new_callable=AsyncMock
    ) as mock_chroma:
        mock_chroma.similarity_search.return_value = mock_results
        result = await AriesTools.search_memory_palace.ainvoke(
            {"query": "color", "username": "u1"}
        )
        assert "color: Blue" in result


@pytest.mark.asyncio
async def test_search_memory_palace_no_results():
    """Verify message when semantic search returns no hits."""
    with patch(
        "app.services.aries.pipeline.tools.chroma_manager", new_callable=AsyncMock
    ) as mock_chroma:
        mock_chroma.similarity_search.return_value = []
        result = await AriesTools.search_memory_palace.ainvoke(
            {"query": "color", "username": "u1"}
        )
        assert "No memories found" in result


@pytest.mark.asyncio
async def test_search_memory_palace_error():
    """Verify error isolation when ChromaDB search fails."""
    with patch(
        "app.services.aries.pipeline.tools.chroma_manager", new_callable=AsyncMock
    ) as mock_chroma:
        mock_chroma.similarity_search.side_effect = Exception("Chroma error")
        result = await AriesTools.search_memory_palace.ainvoke(
            {"query": "color", "username": "u1"}
        )
        assert "Error searching memory" in result
