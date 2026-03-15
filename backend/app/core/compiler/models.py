"""Request and response models for the Compiler feature slice.

This module defines the Pydantic models used to validate internal
service communications and external API requests for code execution.
"""

from pydantic import BaseModel, Field


class RunPythonRequest(BaseModel):
    """Payload to execute arbitrary Python code."""

    code: str = Field(..., description="The Python source code to execute.")
    stdin: str = Field("", description="Standard input to provide to the script.")
    username: str | None = None
    session_id: str | None = None


class RunPythonResponse(BaseModel):
    """Result of an arbitrary Python execution."""

    stdout: str
    stderr: str
    exit_code: int


class TestResult(BaseModel):
    """Detailed result of a single test case evaluation."""

    input: str
    output: str | None = None
    expected: str | None = None
    error: str | None = None
    passed: bool | None = None
    verified: bool | None = None
    is_hidden: bool | None = None
    session_id: str | None = None
    username: str | None = None


class RunExamplesRequest(BaseModel):
    """Payload to test a solution against multiple example cases."""

    code: str
    examples: str
    slug: str | None = None
    expected_outputs: list[str] | None = None
    public_cases_count: int | None = None
    order_independent: bool = False
    username: str | None = None
    session_id: str | None = None


class RunExamplesResponse(BaseModel):
    """Collection of results from a solution test run."""

    results: list[TestResult]
    stderr: str


class AnalyzeSubmissionRequest(BaseModel):
    """Payload for post-execution AI analysis of solution performance."""

    code: str
    slug: str
    results: list[dict]
    stderr: str = ""
    level: int = 1
    username: str | None = None
    session_id: str | None = None


class ValidateSolutionRequest(BaseModel):
    """Payload to request automated test-case generation and validation."""

    title: str
    description: str
    constraints: str
    code: str
