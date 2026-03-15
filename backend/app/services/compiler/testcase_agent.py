"""Agentic service for automated hidden test-case generation.

This module leverages Large Language Models (LLMs) to analyze problem
constraints and generate edge-case-focused test cases that are used
to evaluate user solutions beyond the basic examples.
"""

import json
import logging
import re
from typing import Any

from app.core.config import settings
from groq import Groq

logger = logging.getLogger(__name__)


async def generate_hidden_testcases(
    title: str, description: str, constraints: str, num_cases: int = 5
) -> list[dict[str, Any]]:
    """Analyzes a LeetCode problem and generates robust hidden test cases.

    This function prompts an LLM to act as an elite testing engineer,
    focusing on boundary conditions, empty states, and maximum constraints.

    Args:
        title (str): The title of the problem.
        description (str): Full markdown description of the problem logic.
        constraints (str): Explicit problem constraints (e.g., "1 <= n <= 10^5").
        num_cases (int): The number of unique test cases to generate.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries with 'input' and
            'expected_output' keys. Returns an empty list on failure.
    """
    if not settings.GROQ_API_KEY:
        logger.error("TC_AGENT: GROQ_API_KEY not configured. Skipping generation.")
        return []

    client = Groq(api_key=settings.GROQ_API_KEY)

    system_prompt = f"""You are an elite competitive programmer and testing engineer.
Your task is to generate {num_cases} highly tricky, edge-case focused hidden test cases for a coding problem.

You MUST follow the constraints strictly.
You MUST format your output as a strict JSON object with a single key "testcases" containing an array of objects.

Format Rules:
1. Each object represents ONE complete test case.
2. Keys: "input" (newline-separated arguments) and "expected_output" (JSON serialization).
3. The "input" string MUST represent the exact multiline format LeetCode uses.
4. The "expected_output" MUST be logically verified and strictly serialized.

Example:
{{
  "testcases": [
    {{
      "input": "[2,7,11,15]\\n9",
      "expected_output": "[0,1]"
    }}
  ]
}}
"""

    user_prompt = f"""Problem Title: {title}
Problem Description: {description}
Constraints: {constraints}

Generate exactly {num_cases} hidden test cases evaluating max/min limits and tricky logic edge cases."""

    try:
        response = client.chat.completions.create(
            model=settings.BRAIN_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            return []

        # Robust JSON cleaning
        content = content.strip()
        if "```" in content:
            content = re.sub(r"```[a-z]*\n", "", content)
            content = content.replace("```", "")

        data = json.loads(content.strip())
        return data.get("testcases", [])

    except Exception as e:
        logger.exception(f"TC_AGENT: Generation failed for '{title}': {e}")
        return []
