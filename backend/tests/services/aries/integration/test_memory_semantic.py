import os
import shutil
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from app.infrastructure.aries.chroma_client import ChromaManager
from app.services.aries.memory import memory_service
from langchain_core.embeddings import Embeddings


# Fake embeddings class for testing
class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 768


@pytest.fixture
def test_db_manager():
    # Use a unique temporary directory for EVERY test function
    test_db_dir = f"/tmp/aries_chroma_test_{uuid.uuid4().hex}"
    os.makedirs(test_db_dir, exist_ok=True)

    # Create a fresh manager for this directory
    manager = ChromaManager(persist_directory=test_db_dir)
    manager.embeddings = FakeEmbeddings()

    yield manager

    # Cleanup
    if os.path.exists(test_db_dir):
        shutil.rmtree(test_db_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_memory_semantic_flow(test_db_manager):
    username = "test_user"
    concept = "favorite_language"
    value = "Python"
    session_id = "test_session"

    # Mock at the points of use in memory_service
    with (
        patch("app.services.aries.memory.chroma_manager", test_db_manager),
        patch("app.services.aries.memory.aries_mongo", AsyncMock()),
        patch("app.services.aries.memory.aries_redis", AsyncMock()),
        patch("app.services.aries.memory.brain_adapter", AsyncMock()),
    ):

        # 1. Record a fact
        await memory_service.record_user_fact(username, concept, value)

        # 2. Retrieve context
        with (
            patch(
                "app.services.aries.memory.aries_redis.get_context",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.aries.memory.aries_redis.get_current_code",
                AsyncMock(return_value=""),
            ),
            patch(
                "app.services.aries.memory.aries_redis.get_current_problem",
                AsyncMock(return_value={}),
            ),
            patch(
                "app.services.aries.memory.aries_mongo.get_recent_code_sessions",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.services.aries.memory.aries_mongo.get_recent_episodes",
                AsyncMock(return_value=[]),
            ),
        ):

            context = await memory_service.get_full_context(
                session_id=session_id,
                username=username,
                query="What is my favorite programming language?",
            )

            # 3. Verify
            assert "user_facts" in context
            facts = context["user_facts"]
            assert len(facts) > 0
            assert any(f["content"] == "Python" for f in facts)


@pytest.mark.asyncio
async def test_problem_summary_flow(test_db_manager):
    slug = "two-sum"
    title = "Two Sum"
    description = (
        "Given an array of integers, find two numbers that add up to a specific target."
    )
    session_id = "test_session"
    username = "test_user"

    # Mock at the points of use in memory_service
    with (
        patch("app.services.aries.memory.chroma_manager", test_db_manager),
        patch("app.services.aries.memory.aries_mongo", AsyncMock()),
        patch("app.services.aries.memory.aries_redis", AsyncMock()),
        patch("app.services.aries.memory.brain_adapter", AsyncMock()) as mock_brain,
        patch(
            "app.services.aries.memory.aries_redis.get_current_problem",
            AsyncMock(return_value={"slug": slug}),
        ),
        patch(
            "app.services.aries.memory.aries_redis.get_context",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.aries.memory.aries_mongo.get_recent_code_sessions",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.aries.memory.aries_mongo.get_recent_episodes",
            AsyncMock(return_value=[]),
        ),
    ):

        mock_brain.generate_response = AsyncMock(
            return_value="Find two numbers summing to target."
        )

        # 1. Store problem summary
        await memory_service.summarize_and_store_problem(slug, title, description)

        # 2. Retrieve full context
        context = await memory_service.get_full_context(
            session_id=session_id, username=username, query="Tell me about the problem"
        )

        # 3. Verify
        assert context["problem_summary"] == "Find two numbers summing to target."
