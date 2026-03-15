"""Unit tests for the MCPInfrastructure service.

These tests verify the MCP session management, tool discovery, and execution
logic using mocks for the MCP Python SDK components.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.infrastructure.mcp.client import MCPInfrastructure
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData


@pytest.fixture
def mock_mcp_session():
    """Fixture to provide a mocked MCP ClientSession."""
    mock_session = AsyncMock()

    # Mock list_tools response
    mock_tool = MagicMock()
    mock_tool.name = "get_problem"
    mock_tool.description = "Gets a problem"
    mock_tool.input_schema = {
        "type": "object",
        "properties": {"slug": {"type": "string"}},
    }

    mock_list_tools_res = MagicMock()
    mock_list_tools_res.tools = [mock_tool]
    mock_session.list_tools.return_value = mock_list_tools_res

    # Mock call_tool response
    mock_call_res = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "Problem details"
    mock_call_res.content = [mock_content]
    mock_session.call_tool.return_value = mock_call_res

    return mock_session


@pytest.mark.asyncio
async def test_mcp_get_server_args():
    """Verify construction of server arguments, including environment variables."""
    mcp = MCPInfrastructure()

    # Case 1: No session cookie
    with patch.dict("os.environ", {}, clear=True):
        args = mcp._get_server_args()
        assert "--session-cookie" not in args

    # Case 2: With session cookie
    with patch.dict("os.environ", {"LEETCODE_SESSION": "fake-cookie"}):
        args = mcp._get_server_args()
        assert "--session-cookie" in args
        assert "fake-cookie" in args


@pytest.mark.asyncio
async def test_mcp_get_session_success(mock_mcp_session):
    """Verify successful session initialization and tool discovery."""
    mcp = MCPInfrastructure()

    # Mock transport
    mock_transport = (MagicMock(), MagicMock())  # stdio, write

    with patch(
        "app.infrastructure.mcp.client.stdio_client",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_transport)),
    ):
        with patch(
            "app.infrastructure.mcp.client.ClientSession",
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_mcp_session)),
        ):
            async with mcp.get_session() as (session, groq_tools):
                assert session == mock_mcp_session
                assert len(groq_tools) == 1
                assert groq_tools[0]["function"]["name"] == "get_problem"
                assert groq_tools[0]["function"]["parameters"]["type"] == "object"


@pytest.mark.asyncio
async def test_mcp_get_session_failure():
    """Verify error handling when session initialization fails."""
    mcp = MCPInfrastructure()

    error_data = ErrorData(code=1, message="Connection Failed")
    with patch(
        "app.infrastructure.mcp.client.stdio_client", side_effect=McpError(error_data)
    ):
        with pytest.raises(McpError):
            async with mcp.get_session() as _:
                pass


@pytest.mark.asyncio
async def test_mcp_call_tool_success(mock_mcp_session):
    """Verify tool execution and response parsing."""
    mcp = MCPInfrastructure()

    # Success case with text content
    result = await mcp.call_tool(mock_mcp_session, "get_problem", {"slug": "two-sum"})
    assert result == "Problem details"
    mock_mcp_session.call_tool.assert_called_once_with(
        "get_problem", {"slug": "two-sum"}
    )


@pytest.mark.asyncio
async def test_mcp_call_tool_dict_content(mock_mcp_session):
    """Verify parsing of dictionary-based content blocks."""
    mcp = MCPInfrastructure()

    mock_call_res = MagicMock()
    mock_call_res.content = [{"text": "Dict content"}]
    mock_mcp_session.call_tool.return_value = mock_call_res

    result = await mcp.call_tool(mock_mcp_session, "get_problem", {})
    assert result == "Dict content"


@pytest.mark.asyncio
async def test_mcp_call_tool_error(mock_mcp_session):
    """Verify error isolation when tool execution fails."""
    mcp = MCPInfrastructure()
    mock_mcp_session.call_tool.side_effect = Exception("Tool Crash")

    result = await mcp.call_tool(mock_mcp_session, "bad_tool", {})
    assert "Error executing tool" in result
    assert "Tool Crash" in result
