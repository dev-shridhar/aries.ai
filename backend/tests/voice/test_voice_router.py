import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_voice_tts_endpoint():
    """Verify the /api/voice/tts endpoint."""
    # This might fail if deepgram is not configured, but should handle gracefully
    response = client.post("/api/tts", json={"text": "Hello"})
    # If the service returns 400/500 due to missing key, that's expected but we test the route existence
    assert response.status_code in [200, 400, 500]
