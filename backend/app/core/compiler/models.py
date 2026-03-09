from pydantic import BaseModel


class RunPythonRequest(BaseModel):
    code: str
    stdin: str = ""


class RunPythonResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int


class TestResult(BaseModel):
    input: str
    output: str | None = None
    expected: str | None = None
    error: str | None = None
    passed: bool | None = None
    verified: bool | None = None
    is_hidden: bool | None = None


class RunExamplesRequest(BaseModel):
    code: str
    examples: str
    expected_outputs: list[str] | None = None
    public_cases_count: int | None = None
    order_independent: bool = False


class RunExamplesResponse(BaseModel):
    results: list[TestResult]
    stderr: str


class AnalyzeSubmissionRequest(BaseModel):
    code: str
    slug: str
    results: list[dict]
    stderr: str = ""
    level: int = 1


class ValidateSolutionRequest(BaseModel):
    title: str
    description: str
    constraints: str
    code: str
