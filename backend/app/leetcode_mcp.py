import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com/",
}

_LEETCODE_GRAPHQL = "https://leetcode.com/graphql"

_SEARCH_QUERY = """
query searchProblems($query: String, $limit: Int) {
  questionList(
    categorySlug: ""
    limit: $limit
    skip: 0
    filters: { searchKeywords: $query }
  ) {
    data {
      title
      titleSlug
      difficulty
      topicTags { name }
    }
  }
}
"""

_PROBLEM_QUERY = """
query getProblem($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    title
    titleSlug
    difficulty
    content
    topicTags { name }
    exampleTestcases
    codeSnippets { lang code }
  }
}
"""

_DAILY_QUERY = """
query dailyChallenge {
  activeDailyCodingChallengeQuestion {
    date
    link
    question {
      title
      titleSlug
      difficulty
      content
      topicTags { name }
      exampleTestcases
      codeSnippets { lang code }
    }
  }
}
"""


async def _graphql(query: str, variables: dict = None) -> dict:
    payload = {"query": query, "variables": variables or {}}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_LEETCODE_GRAPHQL, json=payload, headers=_HEADERS)
        resp.raise_for_status()
        body = resp.json()
        if "errors" in body:
            logger.warning("graphql errors: %s", body["errors"])
            return {}
        return body.get("data", {})


def _normalize_stub(snippets: list[dict]) -> str:
    if not snippets:
        return "class Solution:\n    def solve(self):\n        pass"
    for s in snippets:
        if s.get("lang") == "Python3":
            return s["code"]
    return snippets[0]["code"] if snippets else "class Solution:\n    def solve(self):\n        pass"


def _extract_outputs(html: str) -> list[str]:
    outputs = []
    for p in [
        r"<strong>Output:</strong>\s*(?:<pre[^>]*>)?([^<]+)",
        r"<strong>\s*Output:\s*</strong>\s*([^<]+)",
    ]:
        outputs = [m.strip() for m in re.findall(p, html, re.IGNORECASE) if m.strip()]
        if outputs:
            break
    return outputs


async def search_problems(query: str = "", limit: int = 20) -> list[dict]:
    try:
        data = await _graphql(_SEARCH_QUERY, {"query": query, "limit": limit})
        questions = (data.get("questionList") or {}).get("data") or []
        return [
            {
                "slug": q.get("titleSlug", ""),
                "title": q.get("title", ""),
                "difficulty": q.get("difficulty", ""),
                "topics": [t.get("name", "") for t in (q.get("topicTags") or [])],
            }
            for q in questions
        ]
    except Exception as e:
        logger.warning(f"search_problems failed: {e}")
        return []


async def get_problem(slug: str) -> dict:
    try:
        data = await _graphql(_PROBLEM_QUERY, {"titleSlug": slug})
        q = data.get("question")
        if not q:
            return {}
        return {
            "slug": q.get("titleSlug", ""),
            "title": q.get("title", ""),
            "difficulty": q.get("difficulty", ""),
            "content": q.get("content", ""),
            "topics": [t.get("name", "") for t in (q.get("topicTags") or [])],
            "stub": _normalize_stub(q.get("codeSnippets") or []),
            "examples": q.get("exampleTestcases", ""),
            "expected": _extract_outputs(q.get("content", "")),
        }
    except Exception as e:
        logger.warning(f"get_problem failed: {e}")
        return {}


async def get_daily() -> dict:
    try:
        data = await _graphql(_DAILY_QUERY)
        item = data.get("activeDailyCodingChallengeQuestion")
        if not item:
            return {}
        q = item.get("question") or {}
        return {
            "slug": q.get("titleSlug", ""),
            "title": q.get("title", ""),
            "difficulty": q.get("difficulty", ""),
            "content": q.get("content", ""),
            "topics": [t.get("name", "") for t in (q.get("topicTags") or [])],
            "stub": _normalize_stub(q.get("codeSnippets") or []),
            "examples": q.get("exampleTestcases", ""),
            "expected": _extract_outputs(q.get("content", "")),
        }
    except Exception as e:
        logger.warning(f"get_daily failed: {e}")
        return {}
