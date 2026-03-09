import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_mcp_daily_challenge():
    """Verify the /api/mcp/daily endpoint."""
    response = client.get("/api/daily")
    assert response.status_code == 200
    assert "slug" in response.json()


def test_mcp_get_problem():
    """Verify the /api/mcp/problem/{slug} endpoint."""
    response = client.get("/api/problem/two-sum")
    assert response.status_code == 200
    assert response.json()["titleSlug"] == "two-sum"


def test_mcp_search():
    """Verify the /api/mcp/search endpoint."""
    response = client.get("/api/search?query=linked-list")
    assert response.status_code == 200
    assert "problems" in response.json()
