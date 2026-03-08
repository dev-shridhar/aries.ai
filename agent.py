#!/usr/bin/env python3
"""
DSA Agent: Groq (open-source LLM) + LeetCode MCP.
Uses the LeetCode MCP server for all LeetCode data; Groq for reasoning.
Set GROQ_API_KEY in .env or environment.
"""
import asyncio
import json
import os
import sys
from typing import Any, cast

from dotenv import load_dotenv
from groq import Groq

from mcp_leetcode_client import call_leetcode_tool, leetcode_mcp_session

load_dotenv()

SYSTEM_PROMPT = """You are a DSA (Data Structures and Algorithms) assistant. You help users with LeetCode problems.
Use the LeetCode tools to fetch problem details, daily challenge, search problems, user profiles, or solutions when needed.

CRITICAL:
1. DO NOT use placeholder values like "problem-title", "example-slug", or "<slug>" for tool arguments.
2. If the user context provided in the system message includes a "Current Problem" slug, use THAT slug for tools like `get_problem` or `get_solutions`.
3. If you don't have enough information to call a tool (e.g., no slug is provided), ASK the user for the problem name or slug instead of attempting to call the tool with made-up or generic data.
4. If a tool call fails, explain the failure politely to the user and ask for the specific information needed.

Reply in a clear, concise way.

STRICT RESPONSE FORMAT:
Use the following section headers in square brackets to organize your response. Do NOT use hashes (###) or trailing colons.
1. [OVERVIEW]: A brief summary of the problem or your understanding.
2. [LOGIC]: Detailed breakdown of the algorithm or steps.
3. [NEXT_STEPS]: Concrete actions the user should take.
4. [CODE]: If providing code snippets.

Example:
[OVERVIEW]
This problem asks for...

[LOGIC]
1. Use a hash map...
2. Iterate through...

[NEXT_STEPS]
- Implement the hash map...
"""


async def run_agent(user_input: str, user_context: str = None) -> str:
    """Run the agent and return the final response text."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "Error: GROQ_API_KEY not set. Add it to .env or export it."

    client = Groq(api_key=api_key)

    async with leetcode_mcp_session() as (session, groq_tools):
        system_msg = SYSTEM_PROMPT
        if user_context:
            system_msg += f"\n\nUser Context:\n{user_context}"

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_input},
        ]

        while True:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=cast(Any, messages),
                tools=cast(Any, groq_tools),
                tool_choice="auto",
            )
            choice = response.choices[0]
            msg = choice.message
            tool_calls = getattr(msg, "tool_calls", None)

            if tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
                        }
                        for tc in tool_calls
                    ],
                }
                messages.append(assistant_msg)

                for tc in tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result = await call_leetcode_tool(session, name, args)
                    messages.append(
                        {"role": "tool", "tool_call_id": tc.id, "content": result}
                    )
                continue

            return msg.content or ""


def main() -> None:
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    if not user_input:
        print("Usage: python agent.py <your question about LeetCode/DSA>")
        print('Example: python agent.py "What is today\'s daily challenge?"')
        sys.exit(0)

    result = asyncio.run(run_agent(user_input))
    print(result)


if __name__ == "__main__":
    main()
