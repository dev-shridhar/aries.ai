"""API router for the Model Context Protocol (MCP) feature slice.

This module exposes endpoints for LeetCode problem discovery, search,
daily challenges, and detailed metadata retrieval, orchestrating
interactions with MCP servers and unified memory.
"""

import asyncio
import datetime
import json
import logging
import re
from typing import Any

from app.services.aries.memory import memory_service
from app.services.mcp.service import MCPService
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()
mcp_service = MCPService()


def extract_expected_outputs(html_content: str) -> list[str]:
    """Parses problem HTML to extract standard test-case outputs.

    Args:
        html_content (str): The raw HTML description from LeetCode.

    Returns:
        List[str]: A list of extracted output string serializations.
    """
    pattern = r"<strong>Output:</strong>\s*(?:<pre[^>]*>)?([^<]+)"
    matches = re.findall(pattern, html_content)
    outputs = [m.strip() for m in matches if m.strip()]

    if not outputs:
        alt_pattern = r"<strong>\s*Output:\s*</strong>\s*([^<]+)"
        matches = re.findall(alt_pattern, html_content, re.IGNORECASE)
        outputs = [m.strip() for m in matches if m.strip()]

    return outputs


# In-memory transient cache for daily challenge metadata
daily_challenge_cache: dict[str, Any] = {}


@router.get("/daily")
async def get_daily() -> dict[str, Any]:
    """Retrieves the current LeetCode Daily Challenge.

    Caches results for 1 hour to reduce excessive MCP tool calls.

    Returns:
        Dict[str, Any]: Basic challenge metadata (slug, title, date).

    Raises:
        HTTPException: 500 if the MCP tool call or parsing fails.
    """
    global daily_challenge_cache

    now = datetime.datetime.now()
    if (
        daily_challenge_cache
        and (
            now - daily_challenge_cache.get("timestamp", datetime.datetime.min)
        ).total_seconds()
        < 3600
    ):
        return daily_challenge_cache["data"]

    try:
        async with mcp_service.get_session() as (session, _):
            raw = await mcp_service.call_tool(session, "get_daily_challenge", {})

        data = json.loads(raw)
        problem = data.get("problem", data)
        question = (
            (problem.get("question") or problem) if isinstance(problem, dict) else {}
        )

        if isinstance(question, dict):
            slug = (
                question.get("titleSlug")
                or (problem.get("link") or "").strip("/").split("/")[-1]
            )
            title = question.get("title", "")
        else:
            slug = (problem.get("link") or "").strip("/").split("/")[-1]
            title = ""

        result = {"slug": slug, "title": title, "date": data.get("date", "")}
        daily_challenge_cache = {"data": result, "timestamp": now}
        return result
    except Exception as e:
        logger.error(f"API: get_daily failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch daily challenge.")


@router.get("/search")
async def search_problems(
    q: str = "", difficulty: str | None = None, limit: int = 15
) -> dict[str, list[dict[str, Any]]]:
    """Searches for LeetCode problems based on keywords and difficulty.

    Args:
        q (str): Keyword search query.
        difficulty (Optional[str]): Difficulty filter (EASY, MEDIUM, HARD).
        limit (int): Maximum number of results to return.

    Returns:
        Dict[str, List[Dict[str, Any]]]: A list of matching problem summaries.

    Raises:
        HTTPException: 500 if the search tool fails.
    """
    try:
        args = {"limit": limit, "offset": 0}
        if q:
            args["searchKeywords"] = q
        if difficulty and difficulty.upper() in ("EASY", "MEDIUM", "HARD"):
            args["difficulty"] = difficulty.upper()

        async with mcp_service.get_session() as (session, _):
            raw = await mcp_service.call_tool(session, "search_problems", args)

        data = json.loads(raw)
        problems = (
            (data.get("problems") or data).get("questions", [])
            if isinstance(data, dict)
            else []
        )

        # Unified Memory: Log search intent (autonomous learning)
        asyncio.create_task(
            memory_service.record_event(
                session_id="default-session",
                username="anonymous",
                event_type="SEARCH_PROBLEMS",
                details={"query": q, "results_count": len(problems)},
            )
        )

        return {
            "problems": [
                {
                    "titleSlug": p.get("titleSlug"),
                    "title": p.get("title"),
                    "difficulty": p.get("difficulty"),
                    "topicTags": p.get("topicTags", []),
                }
                for p in problems
            ]
        }
    except Exception as e:
        logger.error(f"API: search-problems failed for '{q}': {e}")
        raise HTTPException(status_code=500, detail="Problem search operation failed.")


# Global cache for problem summaries to speed up exploration
problems_cache: list[dict[str, Any]] = []


async def preload_problems() -> None:
    """Pre-fills the problems cache with a subset of active LeetCode problems.

    This background task reduces latency for the navigation/exploration UI.
    """
    global problems_cache
    try:
        args = {"limit": 100, "offset": 0}
        async with mcp_service.get_session() as (session, _):
            raw = await mcp_service.call_tool(session, "search_problems", args)

        data = json.loads(raw)
        problems = (
            (data.get("problems") or data).get("questions", [])
            if isinstance(data, dict)
            else []
        )
        problems_cache = [
            {
                "titleSlug": p.get("titleSlug"),
                "title": p.get("title"),
                "difficulty": p.get("difficulty"),
                "topicTags": p.get("topicTags", []),
            }
            for p in problems
        ]
        logger.info(f"MCP_API: Pre-loaded {len(problems_cache)} problems.")
    except Exception as e:
        logger.error(f"MCP_API: Failed to preload problems: {e}")


@router.get("/problems")
async def get_cached_problems() -> dict[str, list[dict[str, Any]]]:
    """Returns the current list of preloaded problem summaries.

    Returns:
        Dict[str, List[Dict[str, Any]]]: A list of cached problem metadata.
    """
    if not problems_cache:
        await preload_problems()
    return {"problems": problems_cache}


@router.get("/problem/{slug}")
async def get_problem(
    slug: str,
    session_id: str | None = Query(None),
    username: str | None = Query(None),
) -> dict[str, Any]:
    """Fetches high-fidelity problem metadata and synchronizes with unified memory.

    This endpoint retrieves:
    1. Problem description (HTML).
    2. Python-specific code snippets/stubs.
    3. Public test cases and expected outputs.
    4. Caching and semantic storage orchestration.

    Args:
        slug (str): Unique URL-friendly identifier for the problem.
        session_id (Optional[str]): Active interaction session.
        username (Optional[str]): Platform user handle.

    Returns:
        Dict[str, Any]: Comprehensive problem object.

    Raises:
        HTTPException: 404 if not found, 500 on execution error.
    """
    try:
        async with mcp_service.get_session() as (session, _):
            raw = await mcp_service.call_tool(
                session, "get_problem", {"titleSlug": slug}
            )

        data = json.loads(raw)
        problem = data.get("problem", data)

        if not problem or not problem.get("title"):
            raise HTTPException(status_code=404, detail=f"Problem '{slug}' not found.")

        html_content = problem.get("content", "")

        # Unified Memory: Log Load Event & Sync Hot Context (Redis)
        if session_id:
            logger.info(
                f"MCP_API: Synchronizing memory for '{slug}' in session {session_id}"
            )
            await memory_service.record_event(
                session_id=session_id,
                username=username or "anonymous",
                event_type="LOAD_PROBLEM",
                details={"slug": slug, "title": problem.get("title")},
            )

            # Update Hot Context for immediate agent recall
            await memory_service.set_current_problem(
                session_id=session_id,
                problem_data={
                    "slug": slug,
                    "title": problem.get("title"),
                    "description": html_content[:500],
                },
            )

            # Trigger Summarization for Semantic Memory (ChromaDB) - Fire and Forget
            asyncio.create_task(
                memory_service.summarize_and_store_problem(
                    slug=slug, title=problem.get("title", ""), description=html_content
                )
            )

        # Extraction and Stub Generation
        snippets = problem.get("codeSnippets") or []
        python_code = next(
            (
                s.get("code", "")
                for s in snippets
                if (s.get("langSlug") or "").lower() == "python3"
            ),
            "",
        )
        if not python_code and snippets:
            python_code = next(
                (
                    s.get("code", "")
                    for s in snippets
                    if "python" in (s.get("langSlug") or "").lower()
                ),
                "",
            )
        problem["pythonStub"] = python_code

        # Logic Parsing for Sandbox Drivers
        if html_content:
            problem["expectedOutputs"] = extract_expected_outputs(html_content)
            problem["orderIndependent"] = "in any order" in html_content.lower()
        else:
            problem["expectedOutputs"] = []
            problem["orderIndependent"] = False

        return problem

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"MCP_API: get_problem failed for '{slug}': {e}")
        raise HTTPException(
            status_code=500, detail="Internal metadata retrieval error."
        )
