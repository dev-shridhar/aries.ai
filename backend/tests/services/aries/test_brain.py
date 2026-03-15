"""Unit tests for the BrainAdapter pipeline service.

These tests verify LLM interaction logic, including Groq and Ollama
providers, streaming, and embedding generation, using mocks to
isolate the reasoning layer.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.aries.pipeline.brain import BrainAdapter
from langchain_core.messages import AIMessage


@pytest.fixture
def brain_adapter():
    """Fixture to provide a BrainAdapter with mocked ChatGroq."""
    with patch("app.services.aries.pipeline.brain.ChatGroq", MagicMock()):
        return BrainAdapter()


@pytest.mark.asyncio
async def test_generate_response_groq(brain_adapter):
    """Verify standard response generation using Groq."""
    brain_adapter.groq_llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="Hi there!")
    )
    result = await brain_adapter.generate_response(
        "Hello", "You are helpful.", provider="groq"
    )
    assert result == "Hi there!"


@pytest.mark.asyncio
async def test_generate_response_groq_failure(brain_adapter):
    """Verify error message when Groq inference fails."""
    brain_adapter.groq_llm.ainvoke.side_effect = Exception("Groq down")
    result = await brain_adapter.generate_response("Hello", "system")
    assert "trouble thinking" in result


@pytest.mark.asyncio
async def test_generate_response_stream_groq(brain_adapter):
    """Verify streaming response generation using Groq."""

    async def mock_stream(messages):
        yield AIMessage(content="Hi")
        yield AIMessage(content=" there")

    brain_adapter.groq_llm.astream = mock_stream
    chunks = []
    async for chunk in brain_adapter.generate_response_stream("Hello", "system"):
        chunks.append(chunk)
    assert "".join(chunks) == "Hi there"


@pytest.mark.asyncio
async def test_generate_response_stream_groq_failure(brain_adapter):
    """Verify error chunk when Groq streaming fails."""
    brain_adapter.groq_llm.astream.side_effect = Exception("Stream snap")
    chunks = []
    async for chunk in brain_adapter.generate_response_stream("Hello", "system"):
        chunks.append(chunk)
    assert any("snag" in c for c in chunks)


@pytest.mark.asyncio
async def test_ollama_inference(brain_adapter):
    """Verify fallback to local Ollama inference."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "Ollama response"}}
        mock_post.return_value = mock_response

        result = await brain_adapter.generate_response(
            "Hello", "system", provider="ollama"
        )
        assert result == "Ollama response"


@pytest.mark.asyncio
async def test_ollama_inference_stream(brain_adapter):
    """Verify fallback to local Ollama streaming inference."""
    mock_response = MagicMock()

    # Simulate streaming lines
    async def mock_iter():
        yield json.dumps({"message": {"content": "Hi"}}).encode()
        yield json.dumps({"message": {"content": "!"}}).encode()

    mock_response.aiter_lines = mock_iter

    with patch("httpx.AsyncClient.stream") as mock_stream:
        mock_stream.return_value.__aenter__.return_value = mock_response

        chunks = []
        async for chunk in brain_adapter.generate_response_stream(
            "Hello", "system", provider="ollama"
        ):
            chunks.append(chunk)

        assert "".join(chunks) == "Hi!"


@pytest.mark.asyncio
async def test_get_embedding_success(brain_adapter):
    """Verify successful vector embedding generation."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2]}
        mock_post.return_value = mock_response

        result = await brain_adapter.get_embedding("test")
        assert result == [0.1, 0.2]


@pytest.mark.asyncio
async def test_get_embedding_failure(brain_adapter):
    """Verify zero-vector fallback on embedding failure."""
    with patch("httpx.AsyncClient.post", side_effect=Exception("Ollama offline")):
        result = await brain_adapter.get_embedding("test")
        assert len(result) == 768
        assert all(v == 0.0 for v in result)


@pytest.mark.asyncio
async def test_convert_history(brain_adapter):
    """Verify conversion of dict-based history to LangChain messages."""
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "system", "content": "be nice"},
        {"role": "aries", "content": "ram!"},
    ]
    messages = brain_adapter._convert_history(history)
    assert len(messages) == 4
    assert messages[0].content == "hello"
    assert messages[1].content == "hi"
    assert messages[2].content == "be nice"
    assert messages[3].content == "ram!"
