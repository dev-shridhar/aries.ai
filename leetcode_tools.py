"""
LeetCode tools mirroring the LeetCode MCP server API.
Uses LeetCode's public GraphQL API (no auth required for problem data).
"""
import json
import httpx

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"


def get_problem(title_slug: str) -> dict:
    """Fetch a single problem by title slug (e.g. 'two-sum')."""
    query = """
    query questionDetail($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        questionId
        title
        titleSlug
        content
        difficulty
        topicTags { name slug }
        exampleTestcases
        codeSnippets { lang langSlug code }
        hints
        sampleTestCase
      }
    }
    """
    with httpx.Client() as client:
        r = client.post(
            LEETCODE_GRAPHQL,
            json={"query": query, "variables": {"titleSlug": title_slug}},
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            return {"error": data["errors"]}
        return data.get("data", {}).get("question") or {}


def get_daily_challenge() -> dict:
    """Fetch today's daily challenge."""
    query = """
    query {
      activeDailyCodingChallengeQuestion {
        date
        link
        question {
          questionId
          title
          titleSlug
          content
          difficulty
          topicTags { name slug }
          exampleTestcases
        }
      }
    }
    """
    with httpx.Client() as client:
        r = client.post(LEETCODE_GRAPHQL, json={"query": query}, timeout=15.0)
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            return {"error": data["errors"]}
        return data.get("data", {}).get("activeDailyCodingChallengeQuestion") or {}


def search_problems(
    category: str = "all-code-essentials",
    tags: list[str] | None = None,
    difficulty: str | None = None,
    search_keywords: str | None = None,
    limit: int = 10,
    offset: int = 0,
) -> dict:
    """Search problems with optional filters."""
    filters = {}
    if difficulty:
        filters["difficulty"] = difficulty
    if tags:
        filters["tags"] = tags
    if search_keywords:
        filters["searchKeywords"] = search_keywords

    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
      ) {
        total
        questions {
          questionId
          title
          titleSlug
          difficulty
          topicTags { name slug }
          isPaidOnly
        }
      }
    }
    """
    variables = {
        "categorySlug": category if category != "all-code-essentials" else "",
        "limit": limit,
        "skip": offset,
        "filters": filters or None,
    }
    with httpx.Client() as client:
        r = client.post(
            LEETCODE_GRAPHQL,
            json={"query": query, "variables": variables},
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            return {"error": data["errors"]}
        return data.get("data", {}).get("problemsetQuestionList") or {}


# Tool registry for the agent: name -> (function, arg_schema for the model)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_problem",
            "description": "Get details of a LeetCode problem by slug (e.g. two-sum, add-two-numbers).",
            "parameters": {
                "type": "object",
                "properties": {"titleSlug": {"type": "string", "description": "Problem URL slug"}},
                "required": ["titleSlug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_challenge",
            "description": "Get today's LeetCode daily challenge problem.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_problems",
            "description": "Search LeetCode problems by category, tags, difficulty, or keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "e.g. algorithms, database"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "e.g. array, dynamic-programming"},
                    "difficulty": {"type": "string", "enum": ["EASY", "MEDIUM", "HARD"]},
                    "searchKeywords": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        },
    },
]


def run_tool(name: str, arguments: dict) -> str:
    """Execute a LeetCode tool by name and return result as string."""
    try:
        if name == "get_problem":
            out = get_problem(arguments.get("titleSlug", ""))
        elif name == "get_daily_challenge":
            out = get_daily_challenge()
        elif name == "search_problems":
            out = search_problems(
                category=arguments.get("category", "all-code-essentials"),
                tags=arguments.get("tags"),
                difficulty=arguments.get("difficulty"),
                search_keywords=arguments.get("searchKeywords"),
                limit=arguments.get("limit", 10),
                offset=arguments.get("offset", 0),
            )
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
        return json.dumps(out, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
