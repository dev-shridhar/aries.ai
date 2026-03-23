import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.services.aries.pipeline.stt import STTAdapter

@pytest.fixture
def stt_adapter():
    return STTAdapter(api_key="fake_key")

@pytest.mark.asyncio
async def test_transcribe_success(stt_adapter):
    audio_bytes = b"fake audio buffer that is long enough" # > 1500 bytes for real test
    # Actually, for the test we can just mock the 1500 check or provide enough bytes
    audio_bytes = b"a" * 2000 
    mock_transcript = "hello world"

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {"transcript": mock_transcript}
                    ]
                }
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.infrastructure.shared_client.shared_http_client.get_client", return_value=mock_client):
        result = await stt_adapter.transcribe(audio_bytes)
        assert result == mock_transcript
        mock_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_transcribe_empty_audio(stt_adapter):
    result = await stt_adapter.transcribe(b"")
    assert result == ""

@pytest.mark.asyncio
async def test_transcribe_failure(stt_adapter):
    audio_bytes = b"a" * 2000
    
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("API Error"))

    with patch("app.infrastructure.shared_client.shared_http_client.get_client", return_value=mock_client):
        result = await stt_adapter.transcribe(audio_bytes)
        assert result == ""
