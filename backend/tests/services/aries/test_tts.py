import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from app.services.aries.pipeline.tts import TTSAdapter

@pytest.fixture
def tts_adapter():
    return TTSAdapter()

@pytest.mark.asyncio
async def test_speak_success(tts_adapter):
    mock_audio = b"fake-audio-bytes"
    
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.content = mock_audio
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.infrastructure.shared_client.shared_http_client.get_client", return_value=mock_client):
        result = await tts_adapter.speak("Hello")
        assert result == mock_audio
        mock_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_speak_failure(tts_adapter):
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock()))

    with patch("app.infrastructure.shared_client.shared_http_client.get_client", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await tts_adapter.speak("Hello")
