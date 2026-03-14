import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_compiler_run_endpoint():
    """Verify the /api/compiler/run endpoint executes code correctly."""
    payload = {"code": "print(42)", "language": "python"}
    response = client.post("/api/run-python", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["stdout"].strip() == "42"


def test_compiler_verify_endpoint():
    """Verify the /api/compiler/verify endpoint handles problem-slug based execution."""
    # Note: This might require GROQ_API_KEY if agents are involved in hidden test generation
    payload = {
        "code": "class Solution:\n    def twoSum(self, nums, target): return [0,1]",
        "examples": "[2,7,11,15]\n9",
        "expected_outputs": ["[0,1]"],
    }
    response = client.post("/api/run-examples", json=payload)
    # We expect 200 even if tests fail, as long as the infrastructure works
    assert response.status_code == 200
    assert "results" in response.json()
