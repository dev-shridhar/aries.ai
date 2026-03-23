"""Infrastructure layer for Model Context Protocol (MCP) integration.

This module manages the lifecycle of MCP sessions, specifically for the
LeetCode server. It handles stdio transport, session initialization,
dynamic tool discovery, and tool execution.
"""

import asyncio
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
    It now supports keeping a session alive to avoid process-spawning latency.
    """

    LEETCODE_SERVER_COMMAND = "npx"

    def __init__(self):
        self._shared_session: ClientSession | None = None
        self._shared_exit_stack: AsyncExitStack | None = None
        self._lock = asyncio.Lock()

    def _get_server_args(self) -> list[str]:
        """Constructs arguments for the LeetCode MCP server."""
        # Use --no-install to speed up npx if already cached.
        # However, for the first time, it might need to install.
        # We use -y to ensure it installs without prompting if needed.
        args = ["-y", "@jinzcdev/leetcode-mcp-server"]
        session_cookie = os.environ.get("LEETCODE_SESSION")
        if session_cookie:
            args.extend(["--session-cookie", session_cookie])
        return args

    async def _ensure_session(self) -> tuple[ClientSession, list[dict[str, Any]]]:
        """Internal method to ensure a shared session is active."""
        from contextlib import AsyncExitStack

        async with self._lock:
            if self._shared_session:
                # We still need metadata, but for execution we just need the session.
                # If we have a session, we assume tools are already discovered or we just return it.
                return self._shared_session, []

            logger.info("MCP_INFRA: Initializing shared MCP session...")
            self._shared_exit_stack = AsyncExitStack()
            
            try:
                server_params = StdioServerParameters(
                    command=self.LEETCODE_SERVER_COMMAND,
                    args=self._get_server_args(),
                    env=dict(os.environ),
                )

                # Establish transport
                stdio_transport = await self._shared_exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                stdio, write = stdio_transport

                # Initialize session
                self._shared_session = await self._shared_exit_stack.enter_async_context(
                    ClientSession(stdio, write)
                )
                await self._shared_session.initialize()

                # Dynamic tool discovery (Groq format)
                list_tools_response = await self._shared_session.list_tools()
                tools = list_tools_response.tools
                
                groq_tools = []
                for tool in tools:
                    schema = (
                        getattr(tool, "input_schema", None)
                        or getattr(tool, "inputSchema", None)
                        or {"type": "object", "properties": {}}
                    )
                    groq_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": schema,
                        },
                    })
                
                logger.info("MCP_INFRA: Shared session established successfully.")
                return self._shared_session, groq_tools

            except Exception as e:
                logger.error(f"MCP_INFRA: Failed to establish shared session: {e}")
                if self._shared_exit_stack:
                    await self._shared_exit_stack.aclose()
                    self._shared_exit_stack = None
                self._shared_session = None
                raise

    @asynccontextmanager
    async def get_session(
        self,
    ) -> AsyncGenerator[tuple[ClientSession, list[dict[str, Any]]], None]:
        """Provides a managed (or shared) MCP session and discovered tool schemas."""
        session, tools = await self._ensure_session()
        # If we just created it, we have tools. If it was shared, tools might be empty.
        # But for the current usage in mcp_tools.py, it expects tools.
        # So we should probably cache tools too.
        if not hasattr(self, "_cached_tools"):
            self._cached_tools = tools
        
        yield session, self._cached_tools

    async def call_tool(
        self, session: ClientSession, name: str, arguments: dict[str, Any]
    ) -> str:
        """Executes a tool on the active MCP session and parses the result."""
        try:
            # Check if session is still alive? ClientSession doesn't have an easy is_alive.
            # We trust the transport for now.
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
            # If it failed due to a closed session, we should clear it.
            if "closed" in str(e).lower() or "connection" in str(e).lower():
                async with self._lock:
                    self._shared_session = None
            return f"Error executing tool {name}: {str(e)}"

    async def shutdown(self):
        """Cleanly shuts down the shared MCP session."""
        async with self._lock:
            if self._shared_exit_stack:
                await self._shared_exit_stack.aclose()
                self._shared_exit_stack = None
                self._shared_session = None
                logger.info("MCP_INFRA: Shared session shut down.")


# Singleton instance for high-level management
mcp_infra = MCPInfrastructure()
