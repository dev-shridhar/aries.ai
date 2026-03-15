"""Unit tests for the AriesRedisClient infrastructure service.

These tests verify the Redis integration for session state, conversation
history, and code context, using mocks to isolate the domain logic
from actual Redis server instances.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.aries.redis_client import AriesRedisClient


@pytest.fixture
def mock_redis():
    """Fixture to provide a mocked Redis client structure."""
    mock_client = MagicMock()

    # Mocking the pipeline context manager correctly for async with
    # In redis-py, .pipeline() is a synchronous method that returns a pipeline object.
    # That pipeline object is an async context manager.
    mock_pipeline = AsyncMock()
    mock_pipeline_context = AsyncMock()
    mock_pipeline_context.__aenter__.return_value = mock_pipeline

    mock_client.pipeline.return_value = mock_pipeline_context

    # Base client methods are async
    mock_client.close = AsyncMock()
    mock_client.lrange = AsyncMock()
    mock_client.set = AsyncMock()
    mock_client.get = AsyncMock()

    return mock_client, mock_pipeline


@pytest.mark.asyncio
async def test_redis_connect(mock_redis):
    """Verify that connection initializes the Redis client."""
    mock_client, _ = mock_redis
    with patch("redis.asyncio.from_url", return_value=mock_client):
        redis_client = AriesRedisClient(host="localhost", port=6379, db=0)
        await redis_client.connect()
        assert redis_client.client is not None
        assert redis_client.url == "redis://localhost:6379/0"


@pytest.mark.asyncio
async def test_redis_disconnect(mock_redis):
    """Verify graceful disconnection."""
    mock_client, _ = mock_redis
    redis_client = AriesRedisClient()
    redis_client.client = mock_client
    await redis_client.disconnect()
    mock_client.close.assert_called_once()
    assert redis_client.client is None


@pytest.mark.asyncio
async def test_redis_add_message(mock_redis):
    """Verify adding a message to the conversation history via pipeline."""
    mock_client, mock_pipeline = mock_redis
    redis_client = AriesRedisClient()
    redis_client.client = mock_client

    await redis_client.add_message("session-123", "user", "Hello Aries")

    mock_pipeline.rpush.assert_called_once()
    mock_pipeline.ltrim.assert_called_once()
    mock_pipeline.expire.assert_called_once()
    mock_pipeline.execute.assert_called_once()

    # Check normalized role in JSON
    args, _ = mock_pipeline.rpush.call_args
    data = json.loads(args[1])
    assert data["role"] == "user"
    assert data["content"] == "Hello Aries"


@pytest.mark.asyncio
async def test_redis_add_message_aries_role(mock_redis):
    """Verify 'aries' role is normalized to 'assistant'."""
    mock_client, mock_pipeline = mock_redis
    redis_client = AriesRedisClient()
    redis_client.client = mock_client

    await redis_client.add_message("session-123", "aries", "Response")

    args, _ = mock_pipeline.rpush.call_args
    data = json.loads(args[1])
    assert data["role"] == "assistant"


@pytest.mark.asyncio
async def test_redis_get_context(mock_redis):
    """Verify retrieval of conversation context."""
    mock_client, _ = mock_redis
    redis_client = AriesRedisClient()
    redis_client.client = mock_client

    mock_client.lrange.return_value = [
        json.dumps({"role": "user", "content": "Hi"}),
        json.dumps({"role": "assistant", "content": "Hello"}),
    ]

    context = await redis_client.get_context("session-123")
    assert len(context) == 2
    assert context[0]["content"] == "Hi"
    mock_client.lrange.assert_called_once()


@pytest.mark.asyncio
async def test_redis_state_management(mock_redis):
    """Verify setting and getting general session state."""
    mock_client, _ = mock_redis
    redis_client = AriesRedisClient()
    redis_client.client = mock_client

    await redis_client.set_state("session-123", "some-state")
    mock_client.set.assert_called_once_with(
        "aries:session:session-123:state", "some-state", ex=3600
    )

    mock_client.get.return_value = "some-state"
    res = await redis_client.get_state("session-123")
    assert res == "some-state"


@pytest.mark.asyncio
async def test_redis_code_context(mock_redis):
    """Verify setting and getting current editor code."""
    mock_client, _ = mock_redis
    redis_client = AriesRedisClient()
    redis_client.client = mock_client

    await redis_client.set_current_code("session-123", "print(1)")
    mock_client.set.assert_called_once_with(
        "aries:session:session-123:code", "print(1)", ex=3600
    )

    mock_client.get.return_value = "print(1)"
    res = await redis_client.get_current_code("session-123")
    assert res == "print(1)"


@pytest.mark.asyncio
async def test_redis_problem_context(mock_redis):
    """Verify setting and getting current LeetCode problem data."""
    mock_client, _ = mock_redis
    redis_client = AriesRedisClient()
    redis_client.client = mock_client

    problem = {"slug": "two-sum", "title": "Two Sum"}
    await redis_client.set_current_problem("session-123", problem)
    mock_client.set.assert_called_once()

    mock_client.get.return_value = json.dumps(problem)
    res = await redis_client.get_current_problem("session-123")
    assert res["slug"] == "two-sum"

    # Test empty problem
    mock_client.get.return_value = None
    res = await redis_client.get_current_problem("session-123")
    assert res is None
