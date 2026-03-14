from app.infrastructure.mcp.client import mcp_infra


class MCPService:
    """
    Service class for interacting with the LeetCode MCP server.
    """

    def get_session(self):
        """Retrieves or initializes the global MCP session."""
        return mcp_infra.get_session()

    async def call_tool(self, session, name, arguments):
        """Asynchronously calls a tool on the MCP server with given arguments."""
        return await mcp_infra.call_tool(session, name, arguments)
