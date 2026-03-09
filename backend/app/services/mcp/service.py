import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError


class MCPService:
    """
    Service class for interacting with the LeetCode MCP server.
    """

    CONNECTION_HELP = (
        "LeetCode MCP server failed to start or closed the connection. "
        "Check the terminal where you ran 'uvicorn' for npm/node errors. "
        "Fixes: (1) Fix npm cache: sudo chown -R $(whoami) ~/.npm "
        "(2) Install Node/npx: node -v, npx -v "
        "(3) Test manually: npx -y @jinzcdev/leetcode-mcp-server (Ctrl+C to stop)"
    )

    LEETCODE_SERVER_COMMAND = "npx"

    @staticmethod
    def _get_server_args() -> list[str]:
        args = ["-y", "@jinzcdev/leetcode-mcp-server"]
        session_cookie = os.environ.get("LEETCODE_SESSION")
        if session_cookie:
            args.extend(["--session-cookie", session_cookie])
        return args

    @staticmethod
    def _format_groq_tool(tool: Any) -> dict:
        schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": schema,
            },
        }

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[tuple[ClientSession, list[dict]], None]:
        """
        Async context manager: starts LeetCode MCP server and yields (session, groq_tools).
        """
        from contextlib import AsyncExitStack

        exit_stack = AsyncExitStack()
        try:
            server_params = StdioServerParameters(
                command=self.LEETCODE_SERVER_COMMAND,
                args=self._get_server_args(),
                env=dict(os.environ),
            )
            stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await exit_stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()

            list_tools_response = await session.list_tools()
            tools = list_tools_response.tools
            groq_tools = [self._format_groq_tool(t) for t in tools]

            yield session, groq_tools
        except McpError as e:
            msg = str(e).strip()
            if "connection closed" in msg.lower() or "connection" in msg.lower():
                raise RuntimeError(f"{self.CONNECTION_HELP} Original error: {msg}") from e
            raise RuntimeError(f"LeetCode MCP error: {msg}") from e
        finally:
            await exit_stack.aclose()

    async def call_tool(self, session: ClientSession, name: str, arguments: dict) -> str:
        """Call a tool on the LeetCode MCP server and return the result as a string."""
        result = await session.call_tool(name, arguments if arguments else {})
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "\n".join(parts) if parts else json.dumps(result)
