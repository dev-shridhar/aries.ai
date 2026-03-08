import json
import logging
import os
from groq import Groq

logger = logging.getLogger(__name__)

async def validate_solution(title: str, description: str, constraints: str, code: str) -> dict:
    """
    Validates a LeetCode solution using Groq LLM.
    Returns a strict JSON dictionary with validation results.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY not set. Cannot validate solution."}

    client = Groq(api_key=api_key)

    system_prompt = """You are a strict, top-tier Data Structures and Algorithms senior engineer.
Your task is to analyze the provided user code for a specific problem and return a strict JSON response validating their solution.
You must ONLY output valid JSON. Do not include any markdown formatting like ```json or trailing text.

Analyze the solution for:
1. Logical correctness.
2. Time and Space complexity.
3. Proper handling of edge cases.

Respond EXACTLY with this JSON schema:
{
  "is_correct": boolean,
  "time_complexity": "O(...)",
  "space_complexity": "O(...)",
  "edge_cases_handled": boolean,
  "feedback": "A concise, professional explanation of the flaws or a generic praise if flawless. Mention specific edge cases if they are missed."
}"""

    user_prompt = f"""Problem Title: {title}

Problem Description:
{description}

Constraints:
{constraints}

User Code:
{code}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        if not content:
            return {"error": "LLM returned empty response."}
            
        return json.loads(content)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Validator Agent JSON: {e}\nContent was: {content}")
        return {"error": "Failed to parse validation results."}
    except Exception as e:
        logger.exception("Validator Agent failed")
        return {"error": f"Validation failed: {str(e)}"}
