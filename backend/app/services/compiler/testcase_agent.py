"""Agentic service for automated hidden test-case generation.

This module leverages Large Language Models (LLMs) to analyze problem
constraints and generate edge-case-focused test cases that are used
to evaluate user solutions beyond the basic examples.
"""

import json
import logging
import re
from typing import Any

from groq import Groq

from app.core.config import settings

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
Your task is to generate {num_cases} tricky, edge-case focused hidden test cases.

You MUST follow constraints strictly.
You MUST format output as JSON with key "testcases" containing an array.

Format Rules:
1. Each object is ONE test case.
2. Keys: "input" (newline-separated) and "expected_output" (JSON).
3. "input" MUST match LeetCode multiline format.
4. "expected_output" MUST be verified and serialized.

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

Generate {num_cases} hidden test cases for edge cases."""

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
