import logging
from fastapi import APIRouter, HTTPException

from app.core.compiler.models import (
    RunExamplesRequest,
    RunExamplesResponse,
    RunPythonRequest,
    RunPythonResponse,
)
from app.core.mcp.models import SubmitRequest
from app.services.compiler.service import CompilerService
from app.services.compiler.testcase_agent import generate_hidden_testcases
from app.services.mcp.service import MCPService
import json

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/run-python", response_model=RunPythonResponse)
async def run_python(req: RunPythonRequest):
    try:
        result = await CompilerService.run_python(req.code, req.stdin)
        return RunPythonResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-examples", response_model=RunExamplesResponse)
async def run_examples(req: RunExamplesRequest):
    try:
        results, err_str = await CompilerService.run_examples(
            req.code,
            req.examples,
            req.expected_outputs or [],
            req.public_cases_count or 9999,
            req.order_independent,
        )
        return RunExamplesResponse(results=results, stderr=err_str)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit", response_model=RunExamplesResponse)
async def submit_code(req: SubmitRequest):
    try:
        mcp = MCPService()
        async with mcp.get_session() as (session, _):
            raw = await mcp.call_tool(session, "get_problem", {"titleSlug": req.slug})

        data = json.loads(raw)
        problem = data.get("problem", data)

        if not problem or not problem.get("exampleTestcases"):
            raise HTTPException(
                status_code=400, detail="Problem or testcases not found"
            )

        import re

        html_content = problem.get("content", "")
        pattern = r"<strong>Output:</strong>\s*(?:<pre[^>]*>)?([^<]+)"
        matches = re.findall(pattern, html_content)
        outputs = [m.strip() for m in matches if m.strip()]
        if not outputs:
            alt_pattern = r"<strong>\s*Output:\s*</strong>\s*([^<]+)"
            matches = re.findall(alt_pattern, html_content, re.IGNORECASE)
            outputs = [m.strip() for m in matches if m.strip()]

        public_cases_count = len(outputs)
        all_examples_text = problem.get("exampleTestcases", "")

        hidden_cases = await generate_hidden_testcases(
            title=problem.get("title", req.slug),
            description=re.sub(r"<[^>]*>?", "", html_content)[:3000],
            constraints="See problem description",
            num_cases=5,
        )

        if hidden_cases:
            for case in hidden_cases:
                if "input" in case and "expected_output" in case:
                    if not all_examples_text.endswith("\n") and all_examples_text:
                        all_examples_text += "\n"
                    all_examples_text += str(case["input"]).strip() + "\n"
                    outputs.append(str(case["expected_output"]).strip())

        results, err_str = await CompilerService.run_examples(
            req.code,
            all_examples_text,
            outputs,
            public_cases_count,
            "in any order" in html_content.lower(),
        )
        return RunExamplesResponse(results=results, stderr=err_str)
    except Exception as e:
        logger.exception("submit failed")
        raise HTTPException(status_code=500, detail=str(e))
