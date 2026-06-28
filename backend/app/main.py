import asyncio
import base64
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.chat_store import chat_store
from app.code_runner import run_python
from app.voice_pipeline import pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await chat_store.connect()
    yield
    await chat_store.disconnect()


app = FastAPI(title="aries.ai", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Voice WebSocket ──

@app.websocket("/ws")
async def voice_ws(ws: WebSocket):
    await ws.accept()
    state = {"session_id": "default", "audio": b"", "code": ""}

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break

            if "text" in msg:
                data = json.loads(msg["text"])

                if "session_id" in data:
                    state["session_id"] = data["session_id"]
                if "code_context" in data:
                    state["code"] = data["code_context"]

                if data.get("event") == "WELCOME":
                    history = await chat_store.get_history(state["session_id"])
                    reply = await pipeline.brain(
                        "Introduce yourself briefly and ask how you can help.",
                        "You are Aries, a DSA tutor. Be concise (1-2 sentences).",
                        history,
                    )
                    audio = await pipeline.tts(reply)
                    await ws.send_json({"text": reply, "audio": base64.b64encode(audio).decode()})

                if data.get("event") == "PROCESS_AUDIO":
                    await asyncio.sleep(0.2)
                    if not state["audio"]:
                        continue
                    history = await chat_store.get_history(state["session_id"])
                    text, reply, audio = await pipeline.process(state["audio"], "You are Aries, a DSA tutor. Be concise.", history)
                    await chat_store.add_turn(state["session_id"], "user", text)
                    await chat_store.add_turn(state["session_id"], "assistant", reply)
                    await ws.send_json({"text": reply, "audio": base64.b64encode(audio).decode()})
                    state["audio"] = b""

            elif "bytes" in msg:
                state["audio"] += msg["bytes"]

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws error")
    finally:
        await ws.close()


# ── REST Endpoints ──

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/problems")
async def search_problems(q: str = "", difficulty: str = "", limit: int = 20):
    """Search LeetCode problems."""
    from app.leetcode_mcp import search_problems
    problems = await search_problems(q, limit)
    if difficulty:
        problems = [p for p in problems if p.get("difficulty", "").upper() == difficulty.upper()]
    return {"problems": problems}


@app.get("/api/problems/{slug}")
async def get_problem(slug: str):
    """Get problem details by slug."""
    from app.leetcode_mcp import get_problem
    data = await get_problem(slug)
    problem = data.get("problem", data)
    if not problem:
        return {"error": "not found"}
    return problem


@app.post("/api/run")
async def run_code(body: dict):
    """Run code against problem test cases."""
    code = body.get("code", "")
    slug = body.get("slug", "")
    examples = body.get("examples", "")
    expected = body.get("expected", [])

    if not code or not slug:
        return {"results": [{"error": "Missing code or slug"}]}

    from app.leetcode_mcp import get_problem
    data = await get_problem(slug)
    problem = data.get("problem", data)
    examples = problem.get("exampleTestcases", "") if not examples else examples

    if not examples:
        return {"results": [{"error": "No test cases found"}]}

    lines = [l for l in examples.split("\n") if l.strip()]
    results = []
    driver_imports = "from typing import *\nfrom collections import *\nfrom heapq import *\nfrom bisect import *\nimport math\nimport json\n\n"

    for i, line in enumerate(lines):
        driver = driver_imports + code + f"""

import inspect
sol = Solution()
method = [m for m in inspect.getmembers(sol, predicate=inspect.ismethod) if not m[0].startswith('__')][0][1]
try:
    inp = json.loads({json.dumps(line)})
    out = method(inp) if not isinstance(inp, list) else method(*inp if isinstance(inp, list) else [inp])
    exp = json.loads({json.dumps(expected[i] if i < len(expected) else "null")}) if i < len(expected) else None
    passed = json.dumps(out, sort_keys=True) == json.dumps(exp, sort_keys=True) if exp is not None else True
    print(json.dumps({{"input": {json.dumps(line)}, "output": json.dumps(out), "expected": json.dumps(exp), "passed": passed}}))
except Exception as e:
    print(json.dumps({{"input": {json.dumps(line)}, "error": str(e), "passed": False}}))
"""
        result = await run_python(driver)
        try:
            parsed = json.loads(result["stdout"].strip())
            results.append(parsed)
        except (json.JSONDecodeError, ValueError):
            results.append({"input": line, "error": result["stderr"][:200], "passed": False})

    return {"results": results}
