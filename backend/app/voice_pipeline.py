import base64
import json
import logging
from groq import AsyncGroq
from deepgram import DeepgramClient
import httpx

from app.config import settings
from app.leetcode_mcp import search_problems, get_problem
from app.code_runner import run_python

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are Aries, a DSA tutor. You have tools to help: search_problems (find LeetCode problems), "
    "get_problem (load problem details), and run_code (test Python solutions against test cases). "
    "Use them proactively when the user asks about problems or wants to test code. Be concise."
)

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_problems",
            "description": "Search LeetCode problems by keyword. Returns a list of matching problems with title, difficulty, and topics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords, e.g. 'two sum'"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_problem",
            "description": "Get full problem details by slug. Returns title, difficulty, content, code stub, test cases, and expected outputs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string", "description": "Problem slug, e.g. 'two-sum'"},
                },
                "required": ["slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Run Python code against a problem's test cases and return results with pass/fail status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Full Python solution code"},
                    "slug": {"type": "string", "description": "Problem slug to test against"},
                },
                "required": ["code", "slug"],
            },
        },
    },
]


async def _execute_tool(name: str, args: dict) -> str:
    try:
        if name == "search_problems":
            result = await search_problems(args.get("query", ""), args.get("limit", 10))
            return json.dumps(result, indent=2)
        if name == "get_problem":
            result = await get_problem(args["slug"])
            return json.dumps(result, indent=2, default=str)
        if name == "run_code":
            code = args["code"]
            slug = args["slug"]
            problem = await get_problem(slug)
            examples = problem.get("examples", "")
            expected = problem.get("expected", [])
            if not examples:
                return json.dumps({"error": "No test cases found for this problem"})

            lines = [l.rstrip("\r") for l in examples.split("\n") if l.strip()]
            stub = problem.get("stub", "")
            paren = stub.split("(")
            if len(paren) > 1:
                sig = paren[1].split(")")[0]
                params = [p.strip() for p in sig.split(",") if p.strip() and p.strip() != "self"]
                arity = max(1, len(params))
            else:
                arity = 1
            groups = [lines[i:i+arity] for i in range(0, len(lines), arity)]
            results = []
            driver_imports = "from typing import *\nfrom collections import *\nfrom heapq import *\nfrom bisect import *\nimport math\nimport json\n\n"
            for i, group in enumerate(groups):
                args_code = ", ".join(f"json.loads({json.dumps(a)})" for a in group)
                exp_val = expected[i] if i < len(expected) else None
                exp_code = f"json.loads({json.dumps(exp_val)})" if exp_val else None
                driver = driver_imports + code + f"""
import inspect
sol = Solution()
method = [m for m in inspect.getmembers(sol, predicate=inspect.ismethod) if not m[0].startswith("__")][0][1]
try:
    args = [{args_code}]
    out = method(*args)
    exp = {exp_code or "None"}
    passed = json.dumps(out, sort_keys=True) == json.dumps(exp, sort_keys=True) if exp is not None else True
    print(json.dumps({{"input": {json.dumps(group)}, "output": out, "expected": exp, "passed": passed}}, default=str))
except Exception as e:
    print(json.dumps({{"input": {json.dumps(group)}, "error": str(e), "passed": False}}))
"""
                result = await run_python(driver)
                try:
                    parsed = json.loads(result["stdout"].strip())
                    results.append(parsed)
                except (json.JSONDecodeError, ValueError):
                    results.append({"input": group, "error": result["stderr"][:200], "passed": False})
            return json.dumps(results, indent=2, default=str)
        return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as e:
        logger.exception(f"tool {name} failed")
        return json.dumps({"error": str(e)})


class VoicePipeline:
    system = _SYSTEM

    def __init__(self):
        self.groq = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.deepgram = DeepgramClient(api_key=settings.DEEPGRAM_API_KEY)

    async def stt(self, audio: bytes) -> str:
        response = await self.deepgram.listen.v1.media.transcribe_file(
            request=audio, model="nova-2", smart_format=True
        )
        return response.results.channels[0].alternatives[0].transcript or ""

    async def brain(self, text: str, system: str, history: list[dict]) -> str:
        messages = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": text})

        for _ in range(5):
            try:
                completion = await self.groq.chat.completions.create(
                    messages=messages,
                    model=settings.BRAIN_MODEL,
                    tools=_TOOLS,
                    parallel_tool_calls=False,
                    timeout=30,
                )
            except Exception as e:
                err_str = str(e)
                if "tool_use_failed" in err_str:
                    logger.warning("tool use failed, retrying without tools: %s", err_str[:120])
                    completion = await self.groq.chat.completions.create(
                        messages=messages, model=settings.BRAIN_MODEL, timeout=30
                    )
                    return completion.choices[0].message.content or ""
                raise

            msg = completion.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""

            messages.append(msg)
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments)
                logger.info("tool call: %s(%s)", tc.function.name, args)
                result = await _execute_tool(tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        return "I encountered too many tool calls. Let me know what you'd like to do next."

    async def tts(self, text: str) -> bytes:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=linear16&container=wav",
                headers={"Authorization": f"Token {settings.DEEPGRAM_API_KEY}", "Content-Type": "application/json"},
                json={"text": text},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.content

    async def process(self, audio: bytes, system: str, history: list[dict]) -> tuple[str, str, bytes]:
        text = await self.stt(audio)
        if not text.strip():
            return "", "", b""
        reply = await self.brain(text, system, history)
        audio_out = await self.tts(reply)
        return text, reply, audio_out


pipeline = VoicePipeline()
