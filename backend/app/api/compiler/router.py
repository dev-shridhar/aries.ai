"""API router for the Compiler feature slice.

This module exposes endpoints for executing arbitrary Python code, running
solutions against example test cases, and performing high-fidelity
submissions with automated hidden test-case generation.
"""

import json
import logging
import re

from fastapi import APIRouter, HTTPException

from app.core.compiler.models import (
    RunExamplesRequest,
    RunExamplesResponse,
    RunPythonRequest,
    RunPythonResponse,
)
from app.core.mcp.models import SubmitRequest
from app.services.aries.memory import memory_service
from app.services.compiler.service import CompilerService
from app.services.compiler.testcase_agent import generate_hidden_testcases
from app.services.mcp.service import MCPService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/run-python", response_model=RunPythonResponse)
async def run_python(req: RunPythonRequest) -> RunPythonResponse:
    """Executes arbitrary Python code and returns the result.

    Args:
        req (RunPythonRequest): Contains the code and optional stdin.

    Returns:
        RunPythonResponse: stdout, stderr, and exit_code.
    """
    try:
        result = await CompilerService.run_python(req.code, req.stdin)

        # Log activity to episodic memory for AI context
        if req.session_id:
            await memory_service.record_code_activity(
                session_id=req.session_id,
                username=req.username or "anonymous",
                code=req.code,
                activity_type="run_raw",
                results=result,
                status="Success" if result["exit_code"] == 0 else "Error",
            )

        return RunPythonResponse(**result)
    except Exception as e:
        logger.error(f"API: run-python failed: {e}")
        raise HTTPException(status_code=500, detail="Internal execution error.")


@router.post("/run-examples", response_model=RunExamplesResponse)
async def run_examples(req: RunExamplesRequest) -> RunExamplesResponse:
    """Evaluates a solution against a set of provided example cases.

    Args:
        req (RunExamplesRequest): Contains the solution, examples, and metadata.

    Returns:
        RunExamplesResponse: Structured results for each test case.
    """
    try:
        results, err_str = await CompilerService.run_examples(
            req.code,
            req.examples,
            req.expected_outputs or [],
            req.public_cases_count or 9999,
            req.order_independent,
        )

        # Synchronize with learning history
        if req.session_id:
            passed_all = all(r.get("passed", False) for r in results)
            await memory_service.record_code_activity(
                session_id=req.session_id,
                username=req.username or "anonymous",
                code=req.code,
                activity_type="run_examples",
                results=results,
                status="Passed" if passed_all else "Failed",
            )

        return RunExamplesResponse(results=results, stderr=err_str)
    except Exception as e:
        logger.error(f"API: run-examples failed: {e}")
        raise HTTPException(status_code=500, detail="Internal test evaluation error.")


@router.post("/submit", response_model=RunExamplesResponse)
async def submit_code(req: SubmitRequest) -> RunExamplesResponse:
    """Performs a comprehensive submission with hidden test-case generation.

    This endpoint orchestrates:
    1. Problem metadata retrieval via MCP.
    2. Public test case extraction from problem HTML.
    3. Automated hidden test-case generation via LLM.
    4. Full-suite evaluation in the sandbox.

    Args:
        req (SubmitRequest): Contains the solution code and problem identifier.

    Returns:
        RunExamplesResponse: Combined results of public and hidden test cases.
    """
    try:
        # 1. Fetch Problem Details from MCP Tooling
        mcp = MCPService()
        async with mcp.get_session() as (session, _):
            raw = await mcp.call_tool(session, "get_problem", {"titleSlug": req.slug})

        data = json.loads(raw)
        problem = data.get("problem", data)

        if not problem or not problem.get("exampleTestcases"):
            raise HTTPException(
                status_code=400, detail="Problem metadata not available for submission."
            )

        # 2. Extract Public Cases from HTML Content
        html_content = problem.get("content", "")
        # Look for standard Output: <pre>... or <strong>Output:</strong>...
        pattern = r"<strong>Output:</strong>\s*(?:<pre[^>]*>)?([^<]+)"
        matches = re.findall(pattern, html_content)
        outputs = [m.strip() for m in matches if m.strip()]

        if not outputs:
            alt_pattern = r"<strong>\s*Output:\s*</strong>\s*([^<]+)"
            matches = re.findall(alt_pattern, html_content, re.IGNORECASE)
            outputs = [m.strip() for m in matches if m.strip()]

        public_cases_count = len(outputs)
        all_examples_text = problem.get("exampleTestcases", "")

        # 3. Generate High-Fidelity Hidden Test Cases
        hidden_cases = await generate_hidden_testcases(
            title=problem.get("title", req.slug),
            description=re.sub(r"<[^>]*>?", "", html_content)[:3000],
            constraints="Refer to description",
            num_cases=5,
        )

        # Merge hidden cases into the execution buffer
        if hidden_cases:
            for case in hidden_cases:
                if "input" in case and "expected_output" in case:
                    if not all_examples_text.endswith("\n") and all_examples_text:
                        all_examples_text += "\n"
                    all_examples_text += str(case["input"]).strip() + "\n"
                    outputs.append(str(case["expected_output"]).strip())

        # 4. Final Sandbox Execution
        results, err_str = await CompilerService.run_examples(
            req.code,
            all_examples_text,
            outputs,
            public_cases_count,
            "in any order" in html_content.lower(),
        )

        # 5. Persistent Record (Episodic Context)
        if req.session_id:
            passed_all = all(r.get("passed", False) for r in results)
            await memory_service.record_code_activity(
                session_id=req.session_id,
                username=req.username or "anonymous",
                code=req.code,
                activity_type="submit",
                results=results,
                status="Accepted" if passed_all else "Failed",
            )

        return RunExamplesResponse(results=results, stderr=err_str)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"API: submit failed for '{req.slug}': {e}")
        raise HTTPException(
            status_code=500, detail="Internal submission orchestration error."
        )
