"""
MCP client for the LeetCode MCP server.
Spawns the server via stdio (npx @jinzcdev/leetcode-mcp-server) and exposes tools for the agent.
"""
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

CONNECTION_HELP = (
    "LeetCode MCP server failed to start or closed the connection. "
    "Check the terminal where you ran 'uvicorn' for npm/node errors. "
    "Fixes: (1) Fix npm cache: sudo chown -R $(whoami) ~/.npm "
    "(2) Install Node/npx: node -v, npx -v "
    "(3) Test manually: npx -y @jinzcdev/leetcode-mcp-server (Ctrl+C to stop)"
)

# Same command as Cursor's mcp.json for LeetCode
LEETCODE_SERVER_COMMAND = "npx"


def get_server_args() -> list[str]:
    """Return the arguments for starting the LeetCode MCP server, including the session cookie if available."""
    args = ["-y", "@jinzcdev/leetcode-mcp-server"]
    session_cookie = os.environ.get("LEETCODE_SESSION")
    if session_cookie:
        args.extend(["--session-cookie", session_cookie])
    return args


def mcp_tool_to_groq_tool(tool: Any) -> dict:
    """Convert MCP tool to Groq/OpenAI-style tool definition."""
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
async def leetcode_mcp_session():
    """
    Async context manager: starts LeetCode MCP server and yields (session, groq_tools).
    Use session.call_tool(name, arguments) to run tools.
    groq_tools is the list of tools in Groq API format.
    """
    from contextlib import AsyncExitStack

    exit_stack = AsyncExitStack()
    try:
        # Pass full env so npx/npm see same HOME, PATH, nvm/fnm, etc. as your shell
        server_params = StdioServerParameters(
            command=LEETCODE_SERVER_COMMAND,
            args=get_server_args(),
            env=dict(os.environ),
        )
        stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        session = await exit_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()

        list_tools_response = await session.list_tools()
        tools = list_tools_response.tools
        groq_tools = [mcp_tool_to_groq_tool(t) for t in tools]
        print("LeetCode MCP connected; tools:", [t.name for t in tools], file=sys.stderr)

        yield session, groq_tools
    except McpError as e:
        msg = str(e).strip()
        if "connection closed" in msg.lower() or "connection" in msg.lower():
            raise RuntimeError(f"{CONNECTION_HELP} Original error: {msg}") from e
        raise RuntimeError(f"LeetCode MCP error: {msg}") from e
    finally:
        await exit_stack.aclose()


async def call_leetcode_tool(session: ClientSession, name: str, arguments: dict) -> str:
    """Call a tool on the LeetCode MCP server and return the result as a string."""
    result = await session.call_tool(name, arguments if arguments else {})
    # result is CallToolResult with .content list of TextContent
    parts = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
        elif isinstance(block, dict) and "text" in block:
            parts.append(block["text"])
    return "\n".join(parts) if parts else json.dumps(result)
