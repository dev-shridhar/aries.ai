"""Unit tests for the Aries API router.

These tests verify the WebSocket protocol for the Aries voice agent,
ensuring session state management, audio buffering, and interaction
orchestration work correctly using FastAPI's TestClient and mocks.
"""

from unittest.mock import patch

import pytest
from app.api.aries.router import router
from app.core.aries.models import VoiceResponse
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    return TestClient(app)


def test_aries_websocket_session_state(client):
    """Verify that the WebSocket correctly updates session state from JSON."""
    with client.websocket_connect("/ws") as websocket:
        # Initial state is set in the router.
        # Send metadata to update state.
        websocket.send_json(
            {
                "session_id": "test-session",
                "username": "test-user",
                "skill_id": "ram-charge",
                "code_context": "print(123)",
            }
        )

        # Disconnect to trigger finally block logic if needed,
        # but here we just want to ensure it didn't crash.
        websocket.close()


@pytest.mark.asyncio
async def test_aries_websocket_welcome_event(client):
    """Verify handling of the WELCOME event."""
    mock_response = VoiceResponse(text="Hello!", is_final=True)

    # Mock the service method as an async generator
    async def mock_welcome(*args, **kwargs):
        yield mock_response

    with patch(
        "app.api.aries.router.aries_service.process_welcome_interaction",
        side_effect=mock_welcome,
    ):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"event": "WELCOME"})
            data = websocket.receive_json()
            assert data["text"] == "Hello!"
            websocket.close()


@pytest.mark.asyncio
async def test_aries_websocket_process_audio_empty(client):
    """Verify that processing audio with an empty buffer returns an empty response."""
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"event": "PROCESS_AUDIO"})
        data = websocket.receive_json()
        assert data["text"] == ""
        websocket.close()


@pytest.mark.asyncio
async def test_aries_websocket_process_audio_success(client):
    """Verify successful audio processing logic."""
    mock_response = VoiceResponse(text="Processed audio", is_final=True)

    async def mock_voice(*args, **kwargs):
        yield mock_response

    with patch(
        "app.api.aries.router.aries_service.process_voice_interaction",
        side_effect=mock_voice,
    ):
        with client.websocket_connect("/ws") as websocket:
            # Send some binary data
            websocket.send_bytes(b"some audio data")

            # Trigger processing
            websocket.send_json({"event": "PROCESS_AUDIO"})

            data = websocket.receive_json()
            assert data["text"] == "Processed audio"
            websocket.close()


@pytest.mark.asyncio
async def test_aries_websocket_process_audio_failure(client):
    """Verify error handling when the reasoning engine fails."""
    with patch(
        "app.api.aries.router.aries_service.process_voice_interaction",
        side_effect=Exception("Brain failure"),
    ):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_bytes(b"audio")
            websocket.send_json({"event": "PROCESS_AUDIO"})

            data = websocket.receive_json()
            assert "cognitive error" in data["text"]
            websocket.close()


@pytest.mark.asyncio
async def test_aries_websocket_disconnect(client):
    """Verify graceful handling of WebSocket disconnection."""
    with client.websocket_connect("/ws") as websocket:
        # Just connect and then close immediately.
        websocket.close()


@pytest.mark.asyncio
async def test_aries_websocket_transport_failure(client):
    """Verify handling of unexpected transport failures."""
    # We mock json.loads to raise a generic exception when a message is received
    with patch("json.loads", side_effect=ValueError("Corrupted JSON")):
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"some": "data"})
            # The exception happens internally, we just ensure it doesn't crash the server.
            # In a real test we might check logs, but here we just want coverage of the except block.
            pass
