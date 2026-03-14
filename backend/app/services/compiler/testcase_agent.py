import json
import logging
import os

from dotenv import load_dotenv
from groq import Groq

logger = logging.getLogger(__name__)


async def generate_hidden_testcases(
    title: str, description: str, constraints: str, num_cases: int = 5
) -> list[dict]:
    """
    Analyzes a LeetCode problem and generates robust hidden test cases.
    Returns a list of dictionaries with 'input' and 'expected_output' keys.
    """
    load_dotenv()
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY not set. Cannot generate test cases.")
        return []

    client = Groq(api_key=api_key)

    system_prompt = f"""You are an elite competitive programmer and testing engineer.
Your task is to generate {num_cases} highly tricky, edge-case focused hidden test cases for a coding problem.

You MUST follow the constraints strictly.
You MUST format your output as a strict JSON object with a single key "testcases" containing an array of objects. Do not include markdown formatting or ANY other text.

Format Rules:
1. Each object in the "testcases" array represents ONE complete test case.
2. The object MUST have two keys: "input" and "expected_output".
3. The "input" string MUST represent the exact multiline string format LeetCode uses, where multiple arguments are separated by a newline (`\\n`). You MUST correctly deduce the exact number of input arguments the problem expects and output exactly that many lines.
4. The "expected_output" string MUST be the strict JSON representation of the correct answer for that input. You MUST verify the logic mentally or step-by-step; do NOT guess. For example, in a "Two Sum" problem, if you provide `[2,7,11,15]\n1000000000`, the expected output MUST NOT be `[0,1]` as that equals 9, not 1,000,000,000.

Example for a problem expecting 2 arguments (array and int):
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

Problem Description:
{description}

Constraints:
{constraints}

Generate exactly {num_cases} hidden test cases that evaluate maximum limits, minimum limits, empty/null states (if allowed), and tricky logic edge cases."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_object"
            },  # We will prompt for a wrapped object to ensure valid JSON from standard parsing if needed, actually dict wrapping is safer for response_format
        )

        content = response.choices[0].message.content
        if not content:
            return []

        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        data = json.loads(content)
        return data.get("testcases", [])

    except Exception as e:
        logger.exception("Testcase Agent failed")
        return []
