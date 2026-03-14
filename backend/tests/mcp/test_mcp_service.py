import pytest

from app.services.mcp.service import MCPService


@pytest.mark.asyncio
async def test_mcp_connection():
    """Verify we can connect to the LeetCode MCP server."""
    service = MCPService()
    async with service.get_session() as (session, tools):
        assert session is not None
        assert len(tools) > 0
        names = [t["function"]["name"] for t in tools]
        assert "get_problem" in names


@pytest.mark.asyncio
async def test_mcp_get_problem():
    """Verify we can fetch problem details via the service."""
    service = MCPService()
    async with service.get_session() as (session, _):
        result = await service.call_tool(
            session, "get_problem", {"titleSlug": "two-sum"}
        )
        assert "Two Sum" in result
        assert "questionId" in result
