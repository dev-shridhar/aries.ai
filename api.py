"""
Backend API for the DSA Agent frontend.
Run: uvicorn api:app --reload
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)
import json
import re
import tempfile

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq
from pydantic import BaseModel

from agent import run_agent
from validator_agent import validate_solution
from testcase_agent import generate_hidden_testcases
from mcp_leetcode_client import call_leetcode_tool, leetcode_mcp_session
from database import (
    init_db,
    save_user_profile,
    get_user_profile,
    save_recent_submissions,
    get_recent_submissions,
)

load_dotenv()

# Initialize Groq client globally
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    # We don't raise here to allow the app to start,
    # but endpoints using it will check.
    client = None
else:
    client = Groq(api_key=api_key)


app = FastAPI(title="DSA Agent API")

STATIC_DIR = Path(__file__).parent / "static"


def extract_expected_outputs(html_content: str) -> list[str]:
    """Extract expected outputs from LeetCode problem HTML content."""
    # Match patterns like: <strong>Output:</strong> [0,1]
    pattern = r"<strong>Output:</strong>\s*(?:<pre[^>]*>)?([^<]+)"
    matches = re.findall(pattern, html_content)
    outputs = [m.strip() for m in matches if m.strip()]

    # If we couldn't parse outputs, try an alternative pattern
    if not outputs:
        # Try matching with <strong>Output:</strong> followed by any content until <
        alt_pattern = r"<strong>\s*Output:\s*</strong>\s*([^<]+)"
        matches = re.findall(alt_pattern, html_content, re.IGNORECASE)
        outputs = [m.strip() for m in matches if m.strip()]

    return outputs


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    await init_db()


@app.get("/api/debug-mcp-tools")
async def debug_mcp_tools():
    """List available MCP tools for debugging."""
    try:
        async with leetcode_mcp_session() as (session, _):
            tools = await session.list_tools()
            return {"tools": [t.name for t in tools.tools]}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/user-profile")
async def user_profile():
    """Fetch user profile and recent submissions, updating the local cache."""
    try:
        async with leetcode_mcp_session() as (session, _):
            # 1. Get Username first (required for other tools in this server version)
            status_raw = await call_leetcode_tool(session, "get_user_status", {})
            username = None
            try:
                status_data = json.loads(status_raw)
                # Robust extraction: handle both direct username and nested user object
                username = status_data.get("username") or status_data.get(
                    "user", {}
                ).get("username")
            except:
                logger.warning(f"Could not parse username from status: {status_raw}")

            if not username:
                # Fallback: check if session cookie is available as a string "username:session"
                logger.info("Attempting fallback username check...")

            # 2. Fetch Profile
            if username:
                logger.info(f"Syncing profile for username: {username}")
                profile_raw = await call_leetcode_tool(
                    session, "get_user_profile", {"username": username}
                )
                if profile_raw.strip():
                    try:
                        profile_data = json.loads(profile_raw)
                        if profile_data and not profile_data.get("error"):
                            await save_user_profile(profile_data)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode profile JSON: {profile_raw}")

                # 3. Fetch Recent Submissions
                submissions_raw = await call_leetcode_tool(
                    session,
                    "get_recent_submissions",
                    {"username": username, "limit": 10},
                )
                if submissions_raw.strip():
                    try:
                        submissions = json.loads(submissions_raw)
                        if submissions and not submissions.get("error"):
                            await save_recent_submissions(submissions)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to decode submissions JSON: {submissions_raw}"
                        )
            else:
                logger.error("Username missing; cannot sync profile/submissions.")

            # 3. Return combined from DB for consistency
            profile = await get_user_profile()
            recent = await get_recent_submissions()

            return {
                "profile": dict(profile) if profile else None,
                "recent_submissions": [dict(r) for r in recent],
            }
    except Exception as e:
        logger.exception("user_profile failed")
        # Fallback to DB if MCP fails
        profile = await get_user_profile()
        recent = await get_recent_submissions()
        return {
            "profile": dict(profile) if profile else None,
            "recent_submissions": [dict(r) for r in recent],
            "error": str(e),
        }


class ChatRequest(BaseModel):
    message: str
    problem_slug: str | None = None
    problem_title: str | None = None


class ChatResponse(BaseModel):
    response: str


class RunPythonRequest(BaseModel):
    code: str
    stdin: str = ""


class RunPythonResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int


class RunExamplesRequest(BaseModel):
    code: str
    examples: str
    expected_outputs: list[str] | None = None
    public_cases_count: int | None = None
    order_independent: bool = False


class TestResult(BaseModel):
    input: str
    output: str | None = None
    expected: str | None = None
    error: str | None = None
    passed: bool | None = None
    verified: bool | None = None
    is_hidden: bool | None = None


class RunExamplesResponse(BaseModel):
    results: list[TestResult]
    stderr: str


class ExplainRequest(BaseModel):
    title: str
    slug: str


class ExplainResponse(BaseModel):
    response: str


class SubmitRequest(BaseModel):
    code: str
    slug: str


class AnalyzeSubmissionRequest(BaseModel):
    code: str
    slug: str
    results: list[dict]
    stderr: str = ""
    level: int = 1  # 1: Hints, 2: More Hints, 3: Solution (Take Defeat)


class ValidateSolutionRequest(BaseModel):
    title: str
    description: str
    constraints: str
    code: str


@app.get("/api/daily")
async def get_daily():
    """Return today's LeetCode daily challenge (slug + title) from MCP."""
    try:
        async with leetcode_mcp_session() as (session, _):
            raw = await call_leetcode_tool(session, "get_daily_challenge", {})
        data = json.loads(raw)
        problem = data.get("problem", data)
        question = (
            (problem.get("question") or problem) if isinstance(problem, dict) else {}
        )
        if isinstance(question, dict):
            slug = (
                question.get("titleSlug")
                or (problem.get("link") or "").strip("/").split("/")[-1]
            )
            title = question.get("title", "")
        else:
            slug = (problem.get("link") or "").strip("/").split("/")[-1]
            title = ""
        return {"slug": slug, "title": title, "date": data.get("date", "")}
    except Exception as e:
        logger.exception("get_daily failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_problems(
    q: str = "",
    difficulty: str | None = None,
    limit: int = 15,
):
    """Search LeetCode problems via MCP. Returns list of { titleSlug, title, difficulty, topicTags }."""
    try:
        args = {"limit": limit, "offset": 0}
        if q:
            args["searchKeywords"] = q
        if difficulty and difficulty.upper() in ("EASY", "MEDIUM", "HARD"):
            args["difficulty"] = difficulty.upper()
        async with leetcode_mcp_session() as (session, _):
            raw = await call_leetcode_tool(session, "search_problems", args)
        data = json.loads(raw)
        problems = (
            (data.get("problems") or data).get("questions", [])
            if isinstance(data, dict)
            else []
        )
        return {
            "problems": [
                {
                    "titleSlug": p.get("titleSlug"),
                    "title": p.get("title"),
                    "difficulty": p.get("difficulty"),
                    "topicTags": p.get("topicTags", []),
                }
                for p in problems
            ]
        }
    except Exception as e:
        logger.exception("search failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/problem/{slug}")
async def get_problem(slug: str):
    """Fetch a LeetCode problem by slug (e.g. two-sum) from MCP and return JSON for the problem view."""
    try:
        async with leetcode_mcp_session() as (session, _):
            raw = await call_leetcode_tool(session, "get_problem", {"titleSlug": slug})
        data = json.loads(raw)
        problem = data.get("problem", data)
        if not problem or not problem.get("title"):
            raise HTTPException(status_code=404, detail="Problem not found")
        # Ensure we have a Python code snippet for the editor
        snippets = problem.get("codeSnippets") or []
        python_code = ""
        for s in snippets:
            if (s.get("langSlug") or s.get("lang") or "").lower() == "python3":
                python_code = s.get("code", "")
                break
        if not python_code and snippets:
            python_code = next(
                (
                    s.get("code", "")
                    for s in snippets
                    if "python" in (s.get("langSlug") or "").lower()
                ),
                "",
            )
        problem["pythonStub"] = python_code
        
        # Extract Expected Outputs so the frontend can send them back for local execution
        html_content = problem.get("content", "")
        if html_content:
            problem["expectedOutputs"] = extract_expected_outputs(html_content)
            problem["orderIndependent"] = "in any order" in html_content.lower()
        else:
            problem["expectedOutputs"] = []
            problem["orderIndependent"] = False
            
        return problem
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Invalid MCP response: {e}")
    except Exception as e:
        logger.exception("get_problem failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run-python", response_model=RunPythonResponse)
async def run_python(req: RunPythonRequest):
    """Run Python code in a sandboxed subprocess (timeout 5s). Returns stdout, stderr, exit_code."""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Prepend common LeetCode imports
            full_code = (
                "from typing import *\nfrom collections import *\nfrom heapq import *\nfrom bisect import *\nimport math\n\n"
                + req.code
            )
            f.write(full_code)
            path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=req.stdin.encode() if req.stdin else None),
                timeout=5.0,
            )
            return RunPythonResponse(
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                exit_code=proc.returncode or 0,
            )
        finally:
            os.unlink(path)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=400, detail="Execution timed out (max 5s)")
    except Exception as e:
        logger.exception("run_python failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run-examples", response_model=RunExamplesResponse)
async def run_examples(req: RunExamplesRequest):
    """
    Run user code against multiple example test cases.
    We inject a driver script that parses the example strings and calls the Solution method.
    """
    expected_outputs_json = json.dumps(req.expected_outputs or [])
    examples_json = json.dumps(req.examples)
    
    driver_template = r"""
import json
import sys
import inspect
from typing import *
from collections import *
from heapq import *
from bisect import *
import math

# --- User Code ---
__USER_CODE__
# -----------------

def serialize(obj):
    if obj is None: return "null"
    return json.dumps(obj)

def run_all_tests(raw_examples, expected_outputs):
    try:
        if "Solution" not in globals():
            print(json.dumps([{"error": "Class 'Solution' not found."}]))
            return

        sol = Solution()
        methods = [m for m in inspect.getmembers(sol, predicate=inspect.ismethod) 
                   if not m[0].startswith("__")]
        if not methods:
            print(json.dumps([{"error": "No solution method found in Solution class."}]))
            return
        
        name, method = methods[0]
        sig = inspect.signature(method)
        # Exclude 'self' from the parameter count
        n_args = len([p for p in sig.parameters.values() if p.name != 'self'])
        if n_args == 0:
            n_args = 1 # Fallback just in case

        lines = [l for l in raw_examples.split("\n") if l.strip()]
        # Filter out trailing/leading empty lines but preserve internal structure
        while lines and not lines[0].strip(): lines.pop(0)
        while lines and not lines[-1].strip(): lines.pop()
        
        if not lines:
            print(json.dumps([]))
            return

        results = []
        # Each test case uses n_args lines for input
        for i in range(0, len(lines), n_args):
            input_lines = lines[i:i+n_args]
            if len(input_lines) < n_args: break
            
            case_idx = i // n_args
            expected = expected_outputs[case_idx] if case_idx < len(expected_outputs) else None
            
            try:
                args = [json.loads(line) for line in input_lines]
                result_val = method(*args)
                
                passed = True
                expected_serialization = None
                if expected is not None:
                    # expected could be a raw string from HTML or a parsed Python object from Groq
                    if isinstance(expected, str):
                        expected_str = expected.strip()
                        if not expected_str:
                            expected_serialization = None
                        else:
                            try:
                                parsed_expected = json.loads(expected_str)
                            except json.JSONDecodeError:
                                parsed_expected = expected_str
                    else:
                        parsed_expected = expected
                    
                    if expected_serialization is not None or (isinstance(expected, str) and expected.strip()) or not isinstance(expected, str):
                        # Compute passed
                        if isinstance(parsed_expected, str):
                            passed = str(result_val).strip() == parsed_expected.strip()
                        else:
                            # Try strict JSON equality first
                            passed = json.dumps(result_val, sort_keys=True) == json.dumps(parsed_expected, sort_keys=True)
                            
                            # Fallback to order-independent list comparison if allowed
                            if __ORDER_INDEPENDENT__ and not passed and isinstance(result_val, list) and isinstance(parsed_expected, list):
                                try:
                                    passed = sorted(result_val) == sorted(parsed_expected)
                                except Exception:
                                    pass # If lists contain uncomparable types (like nested dicts), ignore this fallback
                        
                        
                        expected_serialization = serialize(parsed_expected)
                
                results.append({
                    "input": "\n".join(input_lines),
                    "expected": expected_serialization,
                    "output": serialize(result_val),
                    "passed": passed,
                    "is_hidden": case_idx >= __PUBLIC_CASES_COUNT__
                })
            except Exception as e:
                results.append({
                    "input": "\n".join(input_lines),
                    "error": str(e),
                    "passed": False,
                    "is_hidden": case_idx >= __PUBLIC_CASES_COUNT__
                })
        
        print(json.dumps(results))
    except Exception as e:
        print(json.dumps([{"error": "Driver error: " + str(e)}]))

if __name__ == "__main__":
    raw = __EXAMPLES_JSON__
    expected = __EXPECTED_JSON__
    run_all_tests(raw, expected)
"""
    driver = driver_template.replace("__USER_CODE__", req.code)
    driver = driver.replace("__EXAMPLES_JSON__", examples_json)
    driver = driver.replace("__EXPECTED_JSON__", expected_outputs_json)
    driver = driver.replace("__PUBLIC_CASES_COUNT__", str(req.public_cases_count or 9999))
    driver = driver.replace("__ORDER_INDEPENDENT__", "True" if req.order_independent else "False")
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(driver)
            path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=10.0,
            )
            out_str = stdout.decode().strip()
            err_str = stderr.decode().strip()

            try:
                # The last line should be our JSON results
                results = json.loads(out_str) if out_str else []
                # Mark as unverified local run
                results = [dict(r) | {"verified": False} for r in results]
                return RunExamplesResponse(results=results, stderr=err_str)
            except json.JSONDecodeError:
                # If it's not JSON, something went wrong (e.g. user print statements)
                # Try to find the JSON array in the output
                import re

                match = re.search(r"\\[.*\\]", out_str, re.DOTALL)
                if match:
                    results = json.loads(match.group(0))
                    # Mark as unverified local run
                    results = [dict(r) | {"verified": False} for r in results]
                    return RunExamplesResponse(results=results, stderr=err_str)
                return RunExamplesResponse(
                    results=[
                        {
                            "input": "All",
                            "error": "Execution failed to return valid JSON. Output: "
                            + out_str,
                            "verified": False,
                        }
                    ],
                    stderr=err_str,
                )
        finally:
            os.unlink(path)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=400, detail="Execution timed out (max 10s)")
    except Exception as e:
        logger.exception("run_examples failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/submit")
async def submit(req: SubmitRequest):
    """
    Submit user code for the given problem.
    Note: Real submission requires LEETCODE_SESSION authentication.
    """
    session_cookie = os.environ.get("LEETCODE_SESSION")
    notice = None

    try:
        async with leetcode_mcp_session() as (mcp_session, _):
            # List tools to see if a real submission tool exists
            tools_resp = await mcp_session.list_tools()
            tool_names = [t.name for t in tools_resp.tools]
            logger.info(f"Available MCP tools: {tool_names}")

            # Look for a submission tool (if any)
            # Prioritize 'submit' over 'test' and exclude common false positives like 'contest'
            candidates = [
                n
                for n in tool_names
                if ("submit" in n.lower() or "test" in n.lower())
                and n not in ["get_problem", "get_user_contest_ranking"]
                and "contest" not in n.lower()
            ]

            # Sort to prioritize tools starting with 'submit'
            candidates.sort(key=lambda x: (not x.lower().startswith("submit"), x))
            submit_tool = candidates[0] if candidates else None

            if submit_tool and session_cookie:
                logger.info(f"Using MCP tool '{submit_tool}' for submission.")
                # Pass the slug and code. Note: argument Names might differ.
                # Common names: questionSlug, titleSlug, code, lang
                raw_result = await call_leetcode_tool(
                    mcp_session,
                    submit_tool,
                    {
                        "questionSlug": req.slug,
                        "titleSlug": req.slug,
                        "code": req.code,
                        "lang": "python3",
                    },
                )
                # If result is JSON-like, we can parse it, otherwise return as results[0].output
                try:
                    res_data = json.loads(raw_result)
                    return {
                        "results": res_data,
                        "stderr": "",
                        "notice": "Verified via MCP.",
                        "debug_info": {"tools": tool_names, "raw_result": raw_result},
                    }
                except:
                    return {
                        "results": [
                            {
                                "input": "Submission",
                                "output": raw_result,
                                "passed": True,
                            }
                        ],
                        "stderr": "",
                        "notice": "Verified via MCP.",
                        "debug_info": {"tools": tool_names, "raw_result": raw_result},
                    }

            # Fallback: Run against examples + AI generated hidden testcases
            notice = "Local submission grading using AI-generated hidden test cases."
            if session_cookie:
                notice += " (Synced with LeetCode account)"
            logger.info("Using AI testcase generator for evaluation")

            raw = await call_leetcode_tool(
                mcp_session, "get_problem", {"titleSlug": req.slug}
            )
            data = json.loads(raw)
            problem = data.get("problem", data)
            examples = problem.get("exampleTestcases", "")
            html_content = problem.get("content", "")
            
            # Start with Public Examples
            all_examples_text = examples
            expected_outputs = extract_expected_outputs(html_content)
            public_cases_count = len(expected_outputs)
            order_independent = "in any order" in html_content.lower()

            # Always generate hidden test cases for robust evaluation
            hidden_cases = await generate_hidden_testcases(
                title=problem.get("title", req.slug),
                description=re.sub(r'<[^>]*>?', '', html_content)[:3000], # strip html
                constraints="See problem description", # Ideally parsed, but this works
                num_cases=12
            )
            
            logger.info(f"Generated {len(hidden_cases) if hidden_cases else 0} hidden test cases via AI.")

            if hidden_cases:
                for case in hidden_cases:
                    if "input" in case and "expected_output" in case:
                        # Ensure each case starts on a new line and args are followed by newlines
                        if not all_examples_text.endswith("\n") and all_examples_text:
                            all_examples_text += "\n"
                        all_examples_text += case["input"].strip() + "\n"
                        # Append the string representation to match HTML parsed expected outputs
                        expected_outputs.append(str(case["expected_output"]).strip())
                logger.info(f"Total test cases to run: {len(expected_outputs)}")

        if not all_examples_text.strip():
            return {
                "results": [],
                "stderr": "",
                "notice": notice or "No test cases found.",
                "debug_info": {"tools": tool_names},
            }

        # Use an official testing tool if available and authenticated
        test_tool = next(
            (n for n in tool_names if n.startswith("test") and "ranking" not in n), None
        )
        if test_tool and session_cookie:
            logger.info(f"Using MCP tool '{test_tool}' for real verification.")
            raw_test_result = await call_leetcode_tool(
                mcp_session,
                test_tool,
                {
                    "titleSlug": req.slug,
                    "code": req.code,
                    "lang": "python3",
                    "testCases": all_examples_text,
                },
            )
            try:
                test_res_data = json.loads(raw_test_result)
                # Mark AI hidden cases so they get badges in UI
                results = []
                for idx, r in enumerate(test_res_data):
                    item = dict(r)
                    if idx >= public_cases_count:
                        item["is_hidden"] = True
                    results.append(item)
                
                return {
                    "results": results,
                    "stderr": "",
                    "notice": "Verified against LeetCode + AI hidden cases!",
                    "debug_info": {"tools": tool_names, "raw_result": raw_test_result},
                }
            except:
                pass

        # Fallback: Run locally
        run_req = RunExamplesRequest(
            code=req.code, 
            examples=all_examples_text.strip(), 
            expected_outputs=expected_outputs,
            public_cases_count=public_cases_count,
            order_independent=order_independent
        )
        res = await run_examples(run_req)
        return {
            "results": [dict(r) for r in res.results],
            "stderr": res.stderr,
            "notice": notice,
            "debug_info": {"tools": tool_names, "problem_data": problem},
        }

    except Exception as e:
        logger.exception("submit failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/explain-problem", response_model=ExplainResponse)
def explain_problem(req: ExplainRequest) -> ExplainResponse:
    """Use Groq (no tools) to explain a specific problem briefly."""
    if not client:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY not set or client failed to initialize",
        )

    prompt = (
        f'Provide a structured coaching guide for the LeetCode problem "{req.title}" (slug: {req.slug}).\n\n'
        f"STRICT RESPONSE FORMAT:\n"
        f"Use these section headers in square brackets on a NEW LINE. Do NOT use colons or hashes.\n\n"
        f"[OVERVIEW]\n[One sentence goal summary]\n\n"
        f"[CONSTRAINTS]\n- [Constraint 1]\n- [Constraint 2]\n\n"
        f"[STRATEGIES]\n1. **[Strategy 1]**: [Details]. (Time: O(...), Space: O(...))\n2. **[Strategy 2]**: [Details]. (Time: O(...), Space: O(...))\n\n"
        f"Keep it concise and encouraging. Do not provide code."
    )
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful DSA tutor. Explain problems clearly and briefly. Use strictly structured headers like [OVERVIEW].",
                },
                {"role": "user", "content": prompt},
            ],
        )
        msg = response.choices[0].message
        return ExplainResponse(response=msg.content or "")
    except Exception as e:
        logger.exception("explain_problem failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    body = await request.body()
    logger.info(f"Raw chat request body: {body.decode()}")
    logger.info(f"ChatRequest object: {req}")
    if not req.message or not req.message.strip():
        logger.warning("Empty message received in chat")
        raise HTTPException(status_code=400, detail="message is required")
    try:
        # Fetch user context from DB for personalization
        profile = await get_user_profile()
        recent = await get_recent_submissions(limit=5)

        user_context = ""
        if req.problem_slug:
            user_context += (
                f"Current Problem: {req.problem_title or req.problem_slug} "
                f"(slug: {req.problem_slug})\n"
            )
        if profile:
            user_context += (
                f"User: {profile['username']} (Ranking: {profile['ranking']})\n"
            )
        if recent:
            user_context += "Recent Solved:\n" + "\n".join(
                [f"- {r['title']} ({r['statusDisplay']})" for r in recent]
            )

        response = await run_agent(
            req.message.strip(), user_context=user_context if user_context else None
        )
        return ChatResponse(response=response)
    except Exception as e:
        logger.exception("POST /api/chat failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-submission")
async def analyze_submission(req: AnalyzeSubmissionRequest):
    """
    Analyze the user's solution after submission.
    Provide tiered feedback based on req.level.
    """
    if not client:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY not set or client failed to initialize",
        )

    # Determine if we can trust the 'passed' status
    is_verified = (
        all(r.get("verified", True) for r in req.results) if req.results else False
    )
    passed = all(r.get("passed") for r in req.results) if req.results else False

    if passed and is_verified and req.level == 1:
        # Success always gets full complexity analysis once
        prompt = (
            f"Analyze this passing LeetCode solution for '{req.slug}':\n\n"
            f"**Code:**\n{req.code}\n\n"
            f"STRICT RESPONSE FORMAT (Use square brackets, NO hashes, NO colons):\n\n"
            f"[ANALYSIS]\nBriefly explain the strategy used.\n\n"
            f"[COMPLEXITY]\n**Time: O(...)**, **Space: O(...)**.\n\n"
            f"[OPTIMIZATION]\nYou MUST rigorously analyze if the code is theoretically optimal. If it is O(N^2) but an O(N) solution exists, aggressively recommend the O(N) approach (e.g. Hash Maps).\n\n"
            f"Keep it professional and concise."
        )
    elif not passed or not is_verified:
        mode_str = (
            "failed"
            if passed == False
            else "executed but NOT verified against expected outputs"
        )
        if req.level == 1:
            prompt = (
                f"The user code for '{req.slug}' {mode_str}. Provide hints to improve it.\n\n"
                f"STRICT RESPONSE FORMAT:\n"
                f"[INFO]\nOne sentence about the status/logic.\n\n"
                f"[HINTS]\n- Hint 1\n- Hint 2\n\n"
                f"Do NOT provide code. Code: {req.code}"
            )
        elif req.level == 2:
            prompt = (
                f"The user is stuck on '{req.slug}'. Provide deeper logical guidance.\n\n"
                f"STRICT RESPONSE FORMAT:\n"
                f"[LOGIC]\nDetailed explanation of the logic needed.\n\n"
                f"[NEXT_STEPS]\nWhat they should try next.\n\n"
                f"Do NOT provide code. Code: {req.code}"
            )
        else:  # Level 3: Take Defeat
            prompt = (
                f"The user has 'Taken Defeat' on '{req.slug}'. You MUST provide the absolute theoretically optimal solution.\n\n"
                f"STRICT RESPONSE FORMAT:\n"
                f"[EXPLANATION]\nDetailed breakdown of the optimal algorithm and why it attains the best possible time and space complexities (e.g. O(N) instead of O(N^2)).\n\n"
                f"[SOLUTION]\nThe optimal Python code solution. MUST be the most efficient approach commonly accepted (e.g. Hash Map instead of Brute Force).\n\n"
                f"[STATS]\nState the final Time and Space Complexity of your optimal code.\n"
            )
    else:
        # Passed but asking for higher level? Just repeat success analysis or provide variations
        return {
            "response": "Your solution already looks great! Focus on the complexity analysis above."
        }

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a top-tier DSA coach. Your goal is to guide users to the solution without giving it away too early. Use strictly structured headers like [LOGIC]. Do NOT use hashes or colons.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        return {"response": response.choices[0].message.content or ""}
    except Exception as e:
        logger.exception("analyze_submission failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/validate-llm")
async def api_validate_solution(req: ValidateSolutionRequest):
    """
    Validates a solution using the dedicated Validator Agent (LLM).
    Returns strict JSON structured feedback.
    """
    try:
        result = await validate_solution(
            title=req.title,
            description=req.description,
            constraints=req.constraints,
            code=req.code
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("api_validate_solution failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/raw-mcp", response_class=PlainTextResponse)
async def raw_mcp(
    tool: str = "search_problems",
    searchKeywords: str | None = None,
    difficulty: str | None = None,
    limit: int = 5,
    offset: int = 0,
):
    """Call a LeetCode MCP tool and return the raw response. Example: /api/raw-mcp?searchKeywords=two%20sum&limit=3"""
    args: dict = {"limit": limit, "offset": offset}
    if searchKeywords:
        args["searchKeywords"] = searchKeywords
    if difficulty and difficulty.upper() in ("EASY", "MEDIUM", "HARD"):
        args["difficulty"] = difficulty.upper()
    try:
        async with leetcode_mcp_session() as (session, _):
            raw = await call_leetcode_tool(session, tool, args)
        return PlainTextResponse(raw)
    except Exception as e:
        logger.exception("raw-mcp failed")
        return PlainTextResponse(f"Error: {e}", status_code=500)


@app.get("/api/debug-mcp", response_class=PlainTextResponse)
async def debug_mcp():
    """Run the LeetCode MCP server briefly and return npx stdout/stderr to diagnose connection issues."""
    proc = await asyncio.create_subprocess_exec(
        "npx",
        "-y",
        "@jinzcdev/leetcode-mcp-server",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=dict(os.environ),
        cwd=Path(__file__).parent,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return PlainTextResponse(
            "Timeout after 8s (server may still be running - that is OK).\n"
            "If the app still shows 'connection closed', check stderr in the terminal where uvicorn is running."
        )
    out = f"exit_code: {proc.returncode}\n\nstdout:\n{stdout.decode() or '(empty)'}\n\nstderr:\n{stderr.decode() or '(empty)'}"
    return PlainTextResponse(out)


@app.get("/", response_class=HTMLResponse)
async def index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse(
            "<h1>DSA Agent API</h1><p>Static files not found. Run from repo root.</p>",
            status_code=404,
        )
    return HTMLResponse(index_file.read_text())
