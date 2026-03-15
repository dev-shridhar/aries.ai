import os
from unittest.mock import AsyncMock, MagicMock, patch

# Mock environment
os.environ["DEEPGRAM_API_KEY"] = "fake_key"
os.environ["GROQ_API_KEY"] = "fake_key"

import pytest

from app.services.aries.pipeline.stt import STTAdapter


@pytest.fixture
def stt_adapter():
    with patch("app.services.aries.pipeline.stt.AsyncDeepgramClient", MagicMock()):
        return STTAdapter(api_key="fake_key")


@pytest.mark.asyncio
async def test_transcribe_success(stt_adapter):
    audio_bytes = b"fake audio"
    mock_transcript = "hello world"

    # Mock the response structure: response.results.channels[0].alternatives[0].transcript
    mock_response = MagicMock()
    mock_channel = MagicMock()
    mock_alternative = MagicMock()
    mock_alternative.transcript = mock_transcript
    mock_channel.alternatives = [mock_alternative]
    mock_response.results.channels = [mock_channel]

    stt_adapter.client.listen.v("1").media.transcribe_file = AsyncMock(
        return_value=mock_response
    )

    result = await stt_adapter.transcribe(audio_bytes)

    assert result == mock_transcript
    stt_adapter.client.listen.v("1").media.transcribe_file.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_empty_audio(stt_adapter):
    result = await stt_adapter.transcribe(b"")
    assert result == ""


@pytest.mark.asyncio
async def test_transcribe_failure(stt_adapter):
    audio_bytes = b"fake audio"
    stt_adapter.client.listen.v("1").media.transcribe_file = AsyncMock(
        side_effect=Exception("API Error")
    )

    result = await stt_adapter.transcribe(audio_bytes)

    assert result == ""
