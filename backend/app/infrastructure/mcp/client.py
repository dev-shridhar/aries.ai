import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

logger = logging.getLogger(__name__)


class MCPInfrastructure:
    LEETCODE_SERVER_COMMAND = "npx"

    def _get_server_args(self) -> list[str]:
        args = ["-y", "@jinzcdev/leetcode-mcp-server"]
        session_cookie = os.environ.get("LEETCODE_SESSION")
        if session_cookie:
            args.extend(["--session-cookie", session_cookie])
        return args

    @asynccontextmanager
    async def get_session(
        self,
    ) -> AsyncGenerator[tuple[ClientSession, list[dict]], None]:
        from contextlib import AsyncExitStack

        exit_stack = AsyncExitStack()
        try:
            server_params = StdioServerParameters(
                command=self.LEETCODE_SERVER_COMMAND,
                args=self._get_server_args(),
                env=dict(os.environ),
            )
            stdio_transport = await exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport
            session = await exit_stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()

            list_tools_response = await session.list_tools()
            tools = list_tools_response.tools

            # Format tool schema for standard AI usage if needed
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
            logger.error(f"MCP Infrastructure error: {e}")
            raise
        finally:
            await exit_stack.aclose()

    async def call_tool(
        self, session: ClientSession, name: str, arguments: dict
    ) -> str:
        result = await session.call_tool(name, arguments if arguments else {})
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "\n".join(parts) if parts else json.dumps(result)


mcp_infra = MCPInfrastructure()
