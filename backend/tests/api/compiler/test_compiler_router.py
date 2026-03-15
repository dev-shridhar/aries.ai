"""Unit tests for the Compiler API router.

These tests verify the API endpoints for code execution and evaluation,
ensuring proper request/response handling and service orchestration.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_run_python_endpoint_success():
    """Verify that the /run-python endpoint correctly orchestrates service calls."""
    mock_response = {"stdout": "42\n", "stderr": "", "exit_code": 0}
    with patch(
        "app.api.compiler.router.CompilerService.run_python", new_callable=AsyncMock
    ) as m1, patch(
        "app.api.compiler.router.memory_service.record_code_activity",
        new_callable=AsyncMock,
    ):
        m1.return_value = mock_response
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/run-python", json={"code": "print(42)", "session_id": "s1"}
            )
        assert response.status_code == 200
        assert response.json()["stdout"].strip() == "42"


@pytest.mark.asyncio
async def test_run_python_endpoint_error():
    """Verify error handling in /run-python."""
    with patch(
        "app.api.compiler.router.CompilerService.run_python",
        side_effect=Exception("Crash"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/run-python", json={"code": "..."})
        assert response.status_code == 500


@pytest.mark.asyncio
async def test_run_examples_endpoint_success():
    """Verify that the /run-examples endpoint handles evaluation requests."""
    mock_results = [{"input": "1\n2", "passed": True, "output": "3", "expected": "3"}]
    with patch(
        "app.api.compiler.router.CompilerService.run_examples", new_callable=AsyncMock
    ) as m1, patch(
        "app.api.compiler.router.memory_service.record_code_activity",
        new_callable=AsyncMock,
    ):
        m1.return_value = (mock_results, "")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/run-examples",
                json={"code": "...", "examples": "1\n2", "session_id": "s1"},
            )
        assert response.status_code == 200
        assert response.json()["results"][0]["passed"] is True


@pytest.mark.asyncio
async def test_submit_endpoint_success():
    """Verify the high-level submission orchestration."""
    mock_problem = {
        "title": "Two Sum",
        "content": "<strong>Output:</strong> 3",
        "exampleTestcases": "1\n2",
    }
    mock_results = [{"input": "1", "output": "3", "expected": "3", "passed": True}]

    with patch("app.api.compiler.router.MCPService.get_session") as mock_mcp_ctx, patch(
        "app.api.compiler.router.MCPService.call_tool", new_callable=AsyncMock
    ) as mock_call, patch(
        "app.api.compiler.router.generate_hidden_testcases", new_callable=AsyncMock
    ) as mock_gen, patch(
        "app.api.compiler.router.CompilerService.run_examples", new_callable=AsyncMock
    ) as mock_run, patch(
        "app.api.compiler.router.memory_service.record_code_activity",
        new_callable=AsyncMock,
    ):

        # Setup MCP Mock
        mock_mcp_ctx.return_value.__aenter__.return_value = (AsyncMock(), None)
        mock_call.return_value = json.dumps({"problem": mock_problem})

        mock_gen.return_value = [{"input": "3\n4", "expected_output": "7"}]
        mock_run.return_value = (mock_results, "")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/submit",
                json={"code": "...", "slug": "two-sum", "session_id": "s1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["results"][0]["input"] == "1"
        assert data["results"][0]["passed"] is True


@pytest.mark.asyncio
async def test_submit_endpoint_no_metadata():
    """Verify error when MCP returns empty problem data."""
    with patch("app.api.compiler.router.MCPService.get_session") as mock_mcp_ctx, patch(
        "app.api.compiler.router.MCPService.call_tool", new_callable=AsyncMock
    ) as mock_call:
        mock_mcp_ctx.return_value.__aenter__.return_value = (AsyncMock(), None)
        mock_call.return_value = json.dumps({})

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/api/submit", json={"code": "...", "slug": "err"})
        assert response.status_code == 400
