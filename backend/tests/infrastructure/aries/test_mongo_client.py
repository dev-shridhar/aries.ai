"""Unit tests for the AriesMongoClient infrastructure service.

These tests verify the MongoDB integration for user profiles, episodic
memory, and semantic fact storage, using mocks to isolate the domain
logic from actual database processes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.infrastructure.aries.mongo_client import AriesMongoClient


@pytest.fixture
def mock_mongo():
    """Fixture to provide a mocked MongoDB client structure."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_client.__getitem__.return_value = mock_db

    # Set up collections as MagicMocks so we can assign and track method calls
    mock_db.episodic_memory = MagicMock()
    mock_db.user_profiles = MagicMock()
    mock_db.code_sessions = MagicMock()
    mock_db.semantic_knowledge = MagicMock()
    mock_db.submissions = MagicMock()

    # Async methods on collections
    mock_db.episodic_memory.insert_one = AsyncMock()
    mock_db.episodic_memory.create_index = AsyncMock()
    mock_db.user_profiles.update_one = AsyncMock()
    mock_db.user_profiles.find_one = AsyncMock()
    mock_db.user_profiles.create_index = AsyncMock()
    mock_db.code_sessions.insert_one = AsyncMock()
    mock_db.code_sessions.create_index = AsyncMock()
    mock_db.semantic_knowledge.update_one = AsyncMock()
    mock_db.semantic_knowledge.create_index = AsyncMock()
    mock_db.submissions.insert_one = AsyncMock()
    mock_db.submissions.create_index = AsyncMock()

    return mock_client, mock_db


@pytest.mark.asyncio
async def test_mongo_connect_and_indexes(mock_mongo):
    """Verify that connection initializes client and creates required indexes."""
    mock_client, mock_db = mock_mongo

    with patch(
        "app.infrastructure.aries.mongo_client.AsyncIOMotorClient",
        return_value=mock_client,
    ):
        mongo = AriesMongoClient(uri="mongodb://localhost:27017", database="aries_test")
        await mongo.connect()

        assert mongo.client is not None
        assert mongo.db is not None

        # Verify indexing calls
        assert mock_db.episodic_memory.create_index.call_count >= 3
        mock_db.user_profiles.create_index.assert_called_once()
        assert mock_db.code_sessions.create_index.call_count >= 4
        assert mock_db.semantic_knowledge.create_index.call_count >= 3
        assert mock_db.submissions.create_index.call_count >= 3


@pytest.mark.asyncio
async def test_mongo_disconnect():
    """Verify graceful disconnection."""
    mongo = AriesMongoClient()
    mock_client = MagicMock()
    mongo.client = mock_client
    await mongo.disconnect()
    mock_client.close.assert_called_once()
    assert mongo.client is None


@pytest.mark.asyncio
async def test_mongo_save_user_profile(mock_mongo):
    """Verify user profile persistence logic."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db

    profile = {"username": "test_user", "email": "test@example.com"}
    await mongo.save_user_profile(profile)

    mock_db.user_profiles.update_one.assert_called_once()
    args, kwargs = mock_db.user_profiles.update_one.call_args
    assert args[0]["username"] == "test_user"
    assert kwargs["upsert"] is True


@pytest.mark.asyncio
async def test_mongo_get_user_profile(mock_mongo):
    """Verify user profile retrieval."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db
    mock_db.user_profiles.find_one.return_value = {"username": "test_user"}

    res = await mongo.get_user_profile("test_user")
    assert res["username"] == "test_user"
    mock_db.user_profiles.find_one.assert_called_once_with({"username": "test_user"})


@pytest.mark.asyncio
async def test_mongo_save_episode(mock_mongo):
    """Verify episodic memory insertion."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db

    await mongo.save_episode("session-1", "user-1", [{"turn": 1}])
    mock_db.episodic_memory.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_mongo_get_recent_episodes(mock_mongo):
    """Verify retrieval of multiple episodes with cursor chaining."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db

    mock_cursor = MagicMock()
    mock_db.episodic_memory.find.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[{"id": 1}])

    res = await mongo.get_recent_episodes("user-1", limit=2)
    assert len(res) == 1
    mock_cursor.to_list.assert_called_once_with(length=2)


@pytest.mark.asyncio
async def test_mongo_save_semantic_fact(mock_mongo):
    """Verify semantic fact updates."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db

    await mongo.save_semantic_fact("recursion", "loops back", "python")
    mock_db.semantic_knowledge.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_mongo_query_semantic_memory(mock_mongo):
    """Verify text-based semantic search with cursors."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db

    mock_cursor = MagicMock()
    mock_db.semantic_knowledge.find.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[])

    await mongo.query_semantic_memory("binary search", skill_id="algos")

    mock_db.semantic_knowledge.find.assert_called_once()
    args, _ = mock_db.semantic_knowledge.find.call_args
    assert args[0]["skill_id"] == "algos"


@pytest.mark.asyncio
async def test_mongo_save_code_session(mock_mongo):
    """Verify code session persistence."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db

    await mongo.save_code_session({"code": "pass"})
    mock_db.code_sessions.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_mongo_get_recent_code_sessions(mock_mongo):
    """Verify retrieval of code sessions with filters and chaining."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db

    mock_cursor = MagicMock()
    mock_db.code_sessions.find.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[])

    await mongo.get_recent_code_sessions(username="test", session_id="123")

    mock_db.code_sessions.find.assert_called_once_with(
        {"username": "test", "session_id": "123"}
    )


@pytest.mark.asyncio
async def test_mongo_save_submission(mock_mongo):
    """Verify leetcode submission logging."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db

    await mongo.save_submission({"status": "Accepted"})
    mock_db.submissions.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_mongo_get_submissions(mock_mongo):
    """Verify retrieval of problem-specific submissions."""
    _, mock_db = mock_mongo
    mongo = AriesMongoClient()
    mongo.db = mock_db

    mock_cursor = MagicMock()
    mock_db.submissions.find.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[])

    await mongo.get_submissions("two-sum")
    mock_db.submissions.find.assert_called_once_with({"problem_slug": "two-sum"})
