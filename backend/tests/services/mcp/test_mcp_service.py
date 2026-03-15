"""Unit tests for the MCPService.

These tests verify the high-level orchestration of MCP tool calls and
session management, ensuring the service layer correctly interacts
with the infrastructure layer using mocks for isolation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.mcp.service import MCPService


@pytest.mark.asyncio
async def test_get_session_orchestration():
    """Verify that the service correctly retrieves a managed MCP session."""
    service = MCPService()
    mock_context = MagicMock()

    with patch(
        "app.infrastructure.mcp.client.MCPInfrastructure.get_session",
        return_value=mock_context,
    ) as mock_infra:
        result = service.get_session()
        assert result == mock_context
        mock_infra.assert_called_once()


@pytest.mark.asyncio
async def test_call_tool_orchestration():
    """Verify that the service correctly delegates tool calls to infrastructure."""
    service = MCPService()
    mock_session = MagicMock()
    mock_response = "Problem Data"

    with patch(
        "app.infrastructure.mcp.client.MCPInfrastructure.call_tool",
        new_callable=AsyncMock,
    ) as mock_call:
        mock_call.return_value = mock_response

        result = await service.call_tool(mock_session, "get_problem", {"slug": "test"})

        assert result == mock_response
        mock_call.assert_called_once_with(mock_session, "get_problem", {"slug": "test"})
