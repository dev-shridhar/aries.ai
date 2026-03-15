"""Unit tests for the TTSAdapter pipeline service.

These tests verify the Deepgram Aura Text-to-Speech integration,
ensuring successful audio generation and proper handling of
API errors using httpx mocks.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.aries.pipeline.tts import TTSAdapter


@pytest.mark.asyncio
async def test_speak_success():
    """Verify successful audio generation from text."""
    adapter = TTSAdapter()
    mock_content = b"fake-wav-data"

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.content = mock_content
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await adapter.speak("Hello")
        assert result == mock_content
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_speak_failure():
    """Verify that HTTP errors are propagated."""
    adapter = TTSAdapter()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="Forbidden", request=MagicMock(), response=mock_response
        )
        mock_post.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.speak("Hello")
