import json
import os
from typing import Any, cast

from groq import Groq

from app.agents.base import BaseAgent
from app.agents.aries_tutor.prompts.system import ARIES_SYSTEM_PROMPT
from app.services.mcp.service import MCPService


class AriesTutorAgent(BaseAgent):
    """
    The Aries Tutor Agent that uses Groq and the MCP LeetCode tool-set to tutor users.
    """

    def __init__(self, mcp_service: MCPService):
        self.api_key = os.environ.get("GROQ_API_KEY")
        self.model = "llama-3.3-70b-versatile"
        self.mcp_service = mcp_service

        if self.api_key:
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None

    async def process_message(
        self,
        user_input: str,
        session_id: str | None = None,
        user_context: str | None = None,
        history: list[dict] | None = None,
    ) -> str:
        if not self.client:
            return "Error: GROQ_API_KEY not set. Add it to .env or export it."

        async with self.mcp_service.get_session() as (session, groq_tools):
            system_msg = ARIES_SYSTEM_PROMPT
            if user_context:
                system_msg += f"\n\nUser Context:\n{user_context}"

            messages = [{"role": "system", "content": system_msg}]

            # Add historical context if available
            if history:
                for msg in history:
                    # Avoid duplicates if history already contains the current user_input
                    if msg["role"] == "user" and msg["content"] == user_input:
                        continue
                    messages.append({"role": msg["role"], "content": msg["content"]})

            # Ensure current user input is at the end if not already added by history logic above
            # (Though logic above skips it to prevent double-adding since we saved it to DB before calling agent)
            if not messages or messages[-1]["content"] != user_input:
                messages.append({"role": "user", "content": user_input})

            while True:
                response = self.client.chat.completions.create(
                    model=self.model,
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
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments or "{}",
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                    messages.append(assistant_msg)

                    for tc in tool_calls:
                        try:
                            args = json.loads(tc.function.arguments or "{}")
                        except json.JSONDecodeError:
                            args = {}
                        result = await self.mcp_service.call_tool(
                            session, tc.function.name, args
                        )
                        messages.append(
                            {"role": "tool", "tool_call_id": tc.id, "content": result}
                        )
                    continue

                return msg.content or ""
