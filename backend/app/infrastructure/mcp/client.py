"""Infrastructure layer for Model Context Protocol (MCP) integration.

This module manages the lifecycle of MCP sessions, specifically for the
LeetCode server. It handles stdio transport, session initialization,
dynamic tool discovery, and tool execution.
"""

import json
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

logger = logging.getLogger(__name__)


class MCPInfrastructure:
    """Handles the low-level connection to MCP servers.

    This class provides an asynchronous context manager to manage
    server connections and utility methods for tool orchestration.
    """

    LEETCODE_SERVER_COMMAND = "npx"

    def _get_server_args(self) -> list[str]:
        """Constructs arguments for the LeetCode MCP server.

        Returns:
            List[str]: Balanced arguments including the optional session cookie.
        """
        args = ["-y", "@jinzcdev/leetcode-mcp-server"]
        session_cookie = os.environ.get("LEETCODE_SESSION")
        if session_cookie:
            args.extend(["--session-cookie", session_cookie])
        return args

    @asynccontextmanager
    async def get_session(
        self,
    ) -> AsyncGenerator[tuple[ClientSession, list[dict[str, Any]]], None]:
        """Provides a managed MCP session and discovered tool schemas.

        Yields:
            Tuple[ClientSession, List[Dict[str, Any]]]: The active session
                and a list of Groq-compatible tool definitions.

        Raises:
            McpError: If server initialization or connection fails.
        """
        from contextlib import AsyncExitStack

        exit_stack = AsyncExitStack()
        try:
            server_params = StdioServerParameters(
                command=self.LEETCODE_SERVER_COMMAND,
                args=self._get_server_args(),
                env=dict(os.environ),
            )

            # Establish transport
            stdio_transport = await exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport

            # Initialize session
            session = await exit_stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()

            # Dynamic tool discovery
            list_tools_response = await session.list_tools()
            tools = list_tools_response.tools

            # Architectural Comment: Format tool schema for Groq tool consumption.
            groq_tools = []
            for tool in tools:
                schema = (
                    getattr(tool, "input_schema", None)
                    or getattr(tool, "inputSchema", None)
                    or {"type": "object", "properties": {}}
                )
                groq_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": schema,
                        },
                    }
                )

            yield session, groq_tools

        except McpError as e:
            logger.error(f"MCP_INFRA: Session failure: {e}")
            raise
        finally:
            await exit_stack.aclose()

    async def call_tool(
        self, session: ClientSession, name: str, arguments: dict[str, Any]
    ) -> str:
        """Executes a tool on the active MCP session and parses the result.

        Args:
            session (ClientSession): The active MCP session.
            name (str): The name of the tool to execute.
            arguments (Dict[str, Any]): Arguments passed to the tool.

        Returns:
            str: The primary text content or JSON-serialized result of the call.
        """
        try:
            result = await session.call_tool(name, arguments if arguments else {})
            parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])

            return "\n".join(parts) if parts else json.dumps(result)
        except Exception as e:
            logger.error(f"MCP_INFRA: Tool call '{name}' failed: {e}")
            return f"Error executing tool {name}: {str(e)}"


# Singleton instance for high-level management
mcp_infra = MCPInfrastructure()
