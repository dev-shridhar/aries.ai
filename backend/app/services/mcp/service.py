"""Domain service for MCP tool orchestration and session management.

This module provides high-level abstractions for interacting with
MCP servers, abstracting the low-level infrastructure transport details.
"""

from typing import Any

from mcp import ClientSession

from app.infrastructure.mcp.client import mcp_infra


class MCPService:
    """Orchestrates interactions with MCP servers.

    This service provides a clean interface for session management and
    tool execution, relying on the infrastructure layer for transport.
    """

    def get_session(self):
        """Retrieves a managed MCP session context.

        Returns:
            AsyncContextManager: A context manager yielding (session, tools).
        """
        return mcp_infra.get_session()

    async def call_tool(
        self, session: ClientSession, name: str, arguments: dict[str, Any]
    ) -> str:
        """Asynchronously calls a tool on the active session.

        Args:
            session (ClientSession): The active MCP session.
            name (str): The name of the tool to execute.
            arguments (Dict[str, Any]): Arguments for the tool call.

        Returns:
            str: The execution result or an error message.
        """
        return await mcp_infra.call_tool(session, name, arguments)
