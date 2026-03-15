import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

# Mock environment
os.environ["DEEPGRAM_API_KEY"] = "fake_key"
os.environ["GROQ_API_KEY"] = "fake_key"

import pytest

from app.services.aries.pipeline.mcp_tools import MCPToolFactory


@asynccontextmanager
async def mock_mcp_session_factory(session=None, tools=None):
    yield session or MagicMock(), tools or []


@pytest.mark.asyncio
async def test_get_tools_filtering():
    # Mock metadata for tools, one public, one not
    mock_tools_metadata = [
        {
            "function": {
                "name": "get_daily_challenge",
                "description": "Get daily challenge",
                "parameters": {"type": "object", "properties": {}},
            }
        },
        {
            "function": {
                "name": "secret_internal_tool",
                "description": "Internal only",
                "parameters": {"type": "object", "properties": {}},
            }
        },
    ]

    with patch("app.services.aries.pipeline.mcp_tools.mcp_infra") as mock_infra:
        # Mock get_session to return our async context manager
        mock_infra.get_session.side_effect = lambda: mock_mcp_session_factory(
            MagicMock(), mock_tools_metadata
        )

        tools = await MCPToolFactory.get_tools()

        assert len(tools) == 1
        assert tools[0].name == "get_daily_challenge"


@pytest.mark.asyncio
async def test_tool_execution_flow():
    mock_tools_metadata = [
        {
            "function": {
                "name": "get_problem",
                "description": "Get problem",
                "parameters": {
                    "type": "object",
                    "properties": {"slug": {"type": "string"}},
                },
            }
        }
    ]

    with patch("app.services.aries.pipeline.mcp_tools.mcp_infra") as mock_infra:
        mock_session = MagicMock()
        mock_infra.get_session.side_effect = lambda: mock_mcp_session_factory(
            mock_session, mock_tools_metadata
        )
        mock_infra.call_tool = AsyncMock(return_value="Problem data")

        tools = await MCPToolFactory.get_tools()
        tool = tools[0]

        # Invoke the tool
        result = await tool.ainvoke({"slug": "two-sum"})

        assert result == "Problem data"
        # Since it calls get_session() again inside tool_fn, call_count will be 2
        assert mock_infra.get_session.call_count == 2
        mock_infra.call_tool.assert_called_once_with(
            mock_session, "get_problem", {"slug": "two-sum"}
        )


@pytest.mark.asyncio
async def test_get_tools_error_handling():
    with patch("app.services.aries.pipeline.mcp_tools.mcp_infra") as mock_infra:
        mock_infra.get_session.side_effect = Exception("MCP Error")

        tools = await MCPToolFactory.get_tools()

        assert tools == []
