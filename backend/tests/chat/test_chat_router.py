import pytest
from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)


def test_chat_endpoint_new_session():
    """Verify the chat endpoint initializes a new session."""
    payload = {"message": "Start a new session please"}
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "session_id" in data


def test_chat_history_retrieval():
    """Verify history can be retrieved for a session."""
    session_id = str(uuid.uuid4())
    response = client.get(f"/api/history/{session_id}")
    assert response.status_code == 200
    assert "history" in response.json()
