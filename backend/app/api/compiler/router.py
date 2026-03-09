import logging
from fastapi import APIRouter, HTTPException

from app.core.compiler.models import (
    RunExamplesRequest,
    RunExamplesResponse,
    RunPythonRequest,
    RunPythonResponse,
)
from app.services.compiler.service import CompilerService

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
