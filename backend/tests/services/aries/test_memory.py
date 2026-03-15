"""Unit tests for the MemoryService.

These tests verify the multi-tier memory architecture coordination
across Redis (hot), ChromaDB (semantic), and MongoDB (episodic).
"""

from unittest.mock import AsyncMock, patch

import pytest
from app.services.aries.memory import memory_service


@pytest.fixture
def mock_clients():
    """Fixture to provide mocked infrastructure clients for MemoryService."""
    with patch(
        "app.services.aries.memory.aries_mongo", new_callable=AsyncMock
    ) as mongo, patch(
        "app.services.aries.memory.chroma_manager", new_callable=AsyncMock
    ) as chroma, patch(
        "app.services.aries.memory.aries_redis", new_callable=AsyncMock
    ) as redis, patch(
        "app.services.aries.memory.brain_adapter", new_callable=AsyncMock
    ) as brain:

        # Default returns
        redis.get_context.return_value = []
        redis.get_current_problem.return_value = None
        redis.get_current_code.return_value = None
        mongo.get_recent_code_sessions.return_value = []
        mongo.get_recent_episodes.return_value = []
        chroma.similarity_search.return_value = []

        yield {"mongo": mongo, "chroma": chroma, "redis": redis, "brain": brain}


@pytest.mark.asyncio
async def test_record_user_fact(mock_clients):
    """Verify that user facts are persisted in semantic memory."""
    await memory_service.record_user_fact("testuser", "hobby", "coding")
    mock_clients["chroma"].add_fact.assert_called_once()
    _, kwargs = mock_clients["chroma"].add_fact.call_args
    assert kwargs["content"] == "coding"
    assert kwargs["metadata"]["username"] == "testuser"


@pytest.mark.asyncio
async def test_summarize_and_store_problem(mock_clients):
    """Verify background summarization of LeetCode problems."""
    mock_clients["brain"].generate_response.return_value = "A summary."
    await memory_service.summarize_and_store_problem("slug", "Title", "Desc")

    mock_clients["brain"].generate_response.assert_called_once()
    mock_clients["chroma"].add_fact.assert_called_once()
    assert mock_clients["chroma"].add_fact.call_args[1]["content"] == "A summary."


@pytest.mark.asyncio
async def test_record_interaction(mock_clients):
    """Verify coordinate record across Redis (history) and Mongo (episodic)."""
    with patch(
        "app.services.aries.pipeline.history.AriesHistoryManager.add_interaction",
        new_callable=AsyncMock,
    ) as mock_hist:
        await memory_service.record_interaction("s1", "u1", "hi", "hello", "skill")
        mock_hist.assert_called_once_with("s1", "hi", "hello")
        mock_clients["mongo"].save_episode.assert_called_once()


@pytest.mark.asyncio
async def test_record_event(mock_clients):
    """Verify system event archival in episodic memory."""
    await memory_service.record_event("s1", "u1", "LOAD", {"id": 1})
    mock_clients["mongo"].save_episode.assert_called_once()


@pytest.mark.asyncio
async def test_set_sensory_state(mock_clients):
    """Verify manual updates to sensory state (code and problem)."""
    await memory_service.set_current_code("s1", "code")
    mock_clients["redis"].set_current_code.assert_called_once_with("s1", "code")

    await memory_service.set_current_problem("s1", {"id": 1})
    mock_clients["redis"].set_current_problem.assert_called_once_with("s1", {"id": 1})


@pytest.mark.asyncio
async def test_record_code_activity(mock_clients):
    """Verify synchronization of execution results across storage tiers."""
    await memory_service.record_code_activity(
        "s1", "u1", "code", "RUN", {"out": "ok"}, "Success"
    )
    mock_clients["redis"].set_current_code.assert_called_once_with("s1", "code")
    mock_clients["mongo"].save_code_session.assert_called_once()


@pytest.mark.asyncio
async def test_get_lightweight_context(mock_clients):
    """Verify high-speed hot context retrieval."""
    mock_clients["redis"].get_context.return_value = [{"role": "u"}]
    ctx = await memory_service.get_lightweight_context("s1")
    assert ctx["history"] == [{"role": "u"}]


@pytest.mark.asyncio
async def test_get_full_context_complex(mock_clients):
    """Verify unified context assembly with multiple tiers and RAG hits."""
    mock_clients["redis"].get_current_problem.return_value = {"slug": "two-sum"}
    mock_clients["chroma"].similarity_search.side_effect = [
        [{"content": "fact", "metadata": {"concept": "c1"}}],  # user_facts
        [{"content": "knowledge", "metadata": {"concept": "k1"}}],  # semantic_hits
        [{"content": "summary"}],  # problem_summaries
    ]

    # Case 1: Success with daily challenge
    with patch("app.api.mcp.router.daily_challenge_cache", {"data": "challenge"}):
        ctx = await memory_service.get_full_context("s1", "u1", query="help")
        assert ctx["problem_summary"] == "summary"
        assert len(ctx["user_facts"]) == 1
        assert ctx["daily_challenge"] == "challenge"

    # Reset side_effect for next case
    mock_clients["chroma"].similarity_search.side_effect = [
        [{"content": "fact", "metadata": {"concept": "c1"}}],
        [{"content": "knowledge", "metadata": {"concept": "k1"}}],
        [{"content": "summary"}],
    ]
    # Case 2: Daily challenge cache lookup failure handling
    with patch("app.api.mcp.router.daily_challenge_cache", None):
        ctx = await memory_service.get_full_context("s1", "u1", query="help")
        assert ctx["daily_challenge"] is None
