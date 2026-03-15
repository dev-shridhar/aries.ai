from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.aries.chroma_client import ChromaManager


@pytest.fixture
def mock_chroma_manager():
    with (
        patch("chromadb.PersistentClient"),
        patch("langchain_chroma.Chroma"),
        patch("langchain_ollama.OllamaEmbeddings"),
    ):
        manager = ChromaManager(persist_directory="/tmp/test_chroma")
        yield manager


@pytest.mark.asyncio
async def test_add_fact(mock_chroma_manager):
    # Setup
    mock_vectorstore = MagicMock()
    # Use AsyncMock for awaited methods
    mock_vectorstore.aadd_texts = AsyncMock(return_value=["fact_1"])

    with patch.object(
        mock_chroma_manager, "get_collection", return_value=mock_vectorstore
    ):
        # Action
        await mock_chroma_manager.add_fact(
            collection_name="test_collection",
            content="test fact",
            metadata={"source": "test"},
            fact_id="fact_1",
        )

        # Assert
        mock_vectorstore.aadd_texts.assert_called_once_with(
            texts=["test fact"], metadatas=[{"source": "test"}], ids=["fact_1"]
        )


@pytest.mark.asyncio
async def test_similarity_search(mock_chroma_manager):
    # Setup
    mock_doc = MagicMock()
    mock_doc.page_content = "found fact"
    mock_doc.metadata = {"score": 0.9}

    mock_vectorstore = MagicMock()
    # Use AsyncMock for awaited methods
    mock_vectorstore.asimilarity_search = AsyncMock(return_value=[mock_doc])

    with patch.object(
        mock_chroma_manager, "get_collection", return_value=mock_vectorstore
    ):
        # Action
        results = await mock_chroma_manager.similarity_search(
            collection_name="test_collection", query="search query", limit=1
        )

        # Assert
        assert len(results) == 1
        assert results[0]["content"] == "found fact"
        mock_vectorstore.asimilarity_search.assert_called_once()
