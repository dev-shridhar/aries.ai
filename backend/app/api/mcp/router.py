import json
import logging
import re
from fastapi import APIRouter, HTTPException

from app.services.mcp.service import MCPService

logger = logging.getLogger(__name__)

router = APIRouter()
mcp_service = MCPService()


def extract_expected_outputs(html_content: str) -> list[str]:
    pattern = r"<strong>Output:</strong>\s*(?:<pre[^>]*>)?([^<]+)"
    matches = re.findall(pattern, html_content)
    outputs = [m.strip() for m in matches if m.strip()]
    if not outputs:
        alt_pattern = r"<strong>\s*Output:\s*</strong>\s*([^<]+)"
        matches = re.findall(alt_pattern, html_content, re.IGNORECASE)
        outputs = [m.strip() for m in matches if m.strip()]
    return outputs


@router.get("/daily")
async def get_daily():
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
        return {"slug": slug, "title": title, "date": data.get("date", "")}
    except Exception as e:
        logger.exception("get_daily failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_problems(q: str = "", difficulty: str | None = None, limit: int = 15):
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
        logger.exception("search failed")
        raise HTTPException(status_code=500, detail=str(e))


problems_cache: list[dict] = []


async def preload_problems():
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
        logger.info(f"Pre-loaded {len(problems_cache)} problems")
    except Exception as e:
        logger.exception("failed to preload problems")


@router.get("/problems")
async def get_cached_problems():
    if not problems_cache:
        await preload_problems()
    return {"problems": problems_cache}


@router.get("/problem/{slug}")
async def get_problem(slug: str):
    try:
        async with mcp_service.get_session() as (session, _):
            raw = await mcp_service.call_tool(
                session, "get_problem", {"titleSlug": slug}
            )
        data = json.loads(raw)
        problem = data.get("problem", data)
        if not problem or not problem.get("title"):
            raise HTTPException(status_code=404, detail="Problem not found")
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

        html_content = problem.get("content", "")
        if html_content:
            problem["expectedOutputs"] = extract_expected_outputs(html_content)
            problem["orderIndependent"] = "in any order" in html_content.lower()
        else:
            problem["expectedOutputs"] = []
            problem["orderIndependent"] = False
        return problem
    except Exception as e:
        logger.exception("get_problem failed")
        raise HTTPException(status_code=500, detail=str(e))
