"""Unit tests for the AriesService orchestrator.

These tests verify the voice interaction pipeline (STT -> Brain -> TTS)
and proactive welcome interactions, ensuring robust error handling
and state management using mocks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.aries.service import AriesService


@pytest.fixture
def mock_aries_deps():
    """Fixture to provide mocked dependencies for AriesService."""
    with (
        patch("app.services.aries.service.stt_adapter", new_callable=AsyncMock) as stt,
        patch("app.services.aries.service.tts_adapter", new_callable=AsyncMock) as tts,
        patch("app.services.aries.service.skill_manager") as skill,
        patch(
            "app.services.aries.service.memory_service", new_callable=AsyncMock
        ) as memory,
        patch(
            "app.services.aries.service.aries_redis", new_callable=AsyncMock
        ) as redis,
        patch("app.services.aries.service.action_trigger") as actions,
    ):

        redis.get_current_problem.return_value = None
        actions.parse_action.return_value = None
        yield {
            "stt": stt,
            "tts": tts,
            "skill": skill,
            "memory": memory,
            "redis": redis,
            "actions": actions,
        }


@pytest.mark.asyncio
async def test_process_voice_interaction_flow(mock_aries_deps):
    """Verify that voice interaction correctly triggers the multi-modal pipeline."""
    aries = AriesService()
    mock_aries_deps["stt"].transcribe.return_value = "how to solve two sum"

    mock_graph = AsyncMock()

    async def mock_astream(*args, **kwargs):
        yield {"agent": {"messages": [MagicMock(content="I can help", tool_calls=[])]}}

    mock_graph.astream = mock_astream

    with patch(
        "app.services.aries.pipeline.graph.get_aries_graph", return_value=mock_graph
    ):
        mock_aries_deps["tts"].speak.return_value = b"audio-data"

        responses = []
        async for resp in aries.process_voice_interaction(b"fake-audio", "sess-123"):
            responses.append(resp)

        assert any(r.text == "how to solve two sum" for r in responses)
        assert any("I can help" in r.text for r in responses)
        assert any(r.audio_chunk is not None for r in responses)


@pytest.mark.asyncio
async def test_process_voice_interaction_empty_audio(mock_aries_deps):
    """Verify response when audio buffer is empty."""
    aries = AriesService()
    responses = []
    async for resp in aries.process_voice_interaction(b"", "sess-123"):
        responses.append(resp)

    assert len(responses) == 1
    assert "didn't hear anything" in responses[0].text


@pytest.mark.asyncio
async def test_process_voice_interaction_noise(mock_aries_deps):
    """Verify that noise/silence skips the reasoning loop."""
    aries = AriesService()
    mock_aries_deps["stt"].transcribe.return_value = "um..."

    responses = []
    async for resp in aries.process_voice_interaction(b"noise-audio", "sess-123"):
        responses.append(resp)

    # One for transcript, one for empty response after noise detection
    assert any(r.text == "um..." for r in responses)
    assert any(r.text == "" and r.is_final is None for r in responses)


@pytest.mark.asyncio
async def test_process_voice_interaction_record_fact(mock_aries_deps):
    """Verify that RECORD_FACT actions are dispatched to memory service."""
    aries = AriesService()
    mock_aries_deps["stt"].transcribe.return_value = "my name is dev"
    mock_aries_deps["actions"].parse_action.return_value = {
        "action": "RECORD_FACT",
        "payload": {"concept": "user_name", "value": "dev"},
    }

    mock_graph = AsyncMock()

    async def mock_astream(*args, **kwargs):
        yield {
            "agent": {"messages": [MagicMock(content="Ok, recorded.", tool_calls=[])]}
        }

    mock_graph.astream = mock_astream

    with patch(
        "app.services.aries.pipeline.graph.get_aries_graph", return_value=mock_graph
    ):
        async for _ in aries.process_voice_interaction(
            b"audio", "sess-123", username="dev"
        ):
            pass

        mock_aries_deps["memory"].record_user_fact.assert_called_once_with(
            username="dev", concept="user_name", value="dev"
        )


@pytest.mark.asyncio
async def test_process_voice_interaction_fatal_error(mock_aries_deps):
    """Verify graceful handling of fatal pipeline exceptions."""
    aries = AriesService()
    mock_aries_deps["stt"].transcribe.side_effect = Exception("STT CRASH")

    responses = []
    async for resp in aries.process_voice_interaction(b"audio", "sess-123"):
        responses.append(resp)

    assert any("temporary logic failure" in r.text for r in responses)


@pytest.mark.asyncio
async def test_process_welcome_interaction_with_problem(mock_aries_deps):
    """Verify welcome greeting when a problem is active in Redis."""
    aries = AriesService()
    mock_aries_deps["redis"].get_current_problem.return_value = {"title": "Two Sum"}

    # Mock brain streaming
    async def mock_gen(*args, **kwargs):
        yield "Hi! Ready for Two Sum?"

    aries.brain.generate_response_stream = mock_gen
    mock_aries_deps["tts"].speak.return_value = b"audio"

    responses = []
    async for resp in aries.process_welcome_interaction("sess-123"):
        responses.append(resp)

    assert any("Two Sum" in r.text for r in responses)


@pytest.mark.asyncio
async def test_process_welcome_interaction_failure(mock_aries_deps):
    """Verify welcome process doesn't crash on error."""
    aries = AriesService()
    mock_aries_deps["redis"].get_current_problem.side_effect = Exception("Redis Down")

    async for _ in aries.process_welcome_interaction("sess-123"):
        pass  # Should not raise exception


def test_is_noise_logic():
    """Verify the internal _is_noise heuristic."""
    aries = AriesService()
    assert aries._is_noise("") is True
    assert aries._is_noise("um") is True
    assert aries._is_noise("uh...") is True
    assert aries._is_noise("Solve the problem") is False
