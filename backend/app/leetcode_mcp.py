import json
import logging

logger = logging.getLogger(__name__)


async def _mcp_call(tool: str, args: dict = None):
    """Call an MCP tool and return the result."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server = StdioServerParameters(command="npx", args=["-y", "@jinzcdev/leetcode-mcp-server"])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args or {})
            return json.loads(result.content[0].text)


def _normalize_problem(raw: dict) -> dict:
    """Normalize LeetCode problem data for the frontend."""
    if not raw:
        return {}
    if isinstance(raw, list):
        return [_normalize_problem(p) for p in raw]
    problem = raw.get("problem", raw)
    question = problem.get("question", problem) if isinstance(problem, dict) else problem
    if not isinstance(question, dict):
        return {}
    return {
        "slug": question.get("titleSlug", ""),
        "title": question.get("title", ""),
        "difficulty": question.get("difficulty", ""),
        "content": question.get("content", ""),
        "topics": [t.get("name", "") for t in (question.get("topicTags") or [])],
        "stub": question.get("codeDefinition", "") or "class Solution:\n    def solve(self):\n        pass",
        "examples": problem.get("exampleTestcases", "") if isinstance(problem, dict) else "",
        "expected": _extract_outputs(question.get("content", "")),
    }


def _extract_outputs(html: str) -> list[str]:
    """Extract expected outputs from problem HTML."""
    import re
    outputs = []
    for p in [r"<strong>Output:</strong>\s*(?:<pre[^>]*>)?([^<]+)", r"<strong>\s*Output:\s*</strong>\s*([^<]+)"]:
        outputs = [m.strip() for m in re.findall(p, html, re.IGNORECASE) if m.strip()]
        if outputs:
            break
    return outputs


async def search_problems(query: str = "", limit: int = 20) -> list[dict]:
    try:
        data = await _mcp_call("search_problems", {"query": query or "", "limit": limit})
        return _normalize_problem(data) if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"search failed: {e}")
        return []


async def get_problem(slug: str) -> dict:
    try:
        data = await _mcp_call("get_problem", {"titleSlug": slug})
        return _normalize_problem(data)
    except Exception as e:
        logger.warning(f"get_problem failed: {e}")
        return {}


async def get_daily() -> dict:
    try:
        data = await _mcp_call("get_daily_challenge", {})
        return _normalize_problem(data)
    except Exception as e:
        logger.warning(f"daily failed: {e}")
        return {}
