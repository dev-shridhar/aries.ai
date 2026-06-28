import json
import logging

logger = logging.getLogger(__name__)


async def search_problems(query: str = "", limit: int = 20) -> list[dict]:
    """Fetch problems from LeetCode via MCP."""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server = StdioServerParameters(command="npx", args=["-y", "@jinzcdev/leetcode-mcp-server"])
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("search_problems", {"query": query or "", "limit": limit})
                return json.loads(result.content[0].text)
    except Exception as e:
        logger.warning(f"mcp search failed: {e}")
        return []


async def get_problem(slug: str) -> dict:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server = StdioServerParameters(command="npx", args=["-y", "@jinzcdev/leetcode-mcp-server"])
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("get_problem", {"titleSlug": slug})
                return json.loads(result.content[0].text)
    except Exception as e:
        logger.warning(f"mcp get_problem failed: {e}")
        return {}


async def get_daily() -> dict:
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server = StdioServerParameters(command="npx", args=["-y", "@jinzcdev/leetcode-mcp-server"])
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("get_daily_challenge", {})
                data = json.loads(result.content[0].text)
                problem = data.get("problem", data) or {}
                q = problem.get("question", problem) if isinstance(problem, dict) else {}
                return {"slug": q.get("titleSlug"), "title": q.get("title")} if isinstance(q, dict) else {}
    except Exception as e:
        logger.warning(f"mcp daily failed: {e}")
        return {}
