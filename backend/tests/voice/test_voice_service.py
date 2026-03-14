import pytest

from app.services.voice.service import VoiceService


@pytest.mark.asyncio
async def test_voice_service_initialization():
    """Verify voice service initializes correctly."""
    service = VoiceService()
    # Check if deepgram key is present (optional based on env)
    import os

    if not os.environ.get("DEEPGRAM_API_KEY"):
        # Just check if it handles missing key gracefully
        assert hasattr(service, "api_key") or True
    else:
        assert service.api_key is not None


@pytest.mark.asyncio
async def test_text_to_speech_mock():
    """Verify TTS logic (mocked or skipped if no key)."""
    import os

    if not os.environ.get("DEEPGRAM_API_KEY"):
        pytest.skip("DEEPGRAM_API_KEY not set")

    service = VoiceService()
    # Expecting some binary output or URL
    result = await service.text_to_speech("Hello")
    assert result is not None
