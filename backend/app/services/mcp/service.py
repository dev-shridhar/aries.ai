from app.infrastructure.mcp.client import mcp_infra


class MCPService:
    """
    Service class for interacting with the LeetCode MCP server.
    """

    def get_session(self):
        return mcp_infra.get_session()

    async def call_tool(self, session, name, arguments):
        return await mcp_infra.call_tool(session, name, arguments)
