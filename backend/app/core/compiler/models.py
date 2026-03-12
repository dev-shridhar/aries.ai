from pydantic import BaseModel


class RunPythonRequest(BaseModel):
    code: str
    stdin: str = ""
    username: Optional[str] = None
    session_id: Optional[str] = None


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
    session_id: Optional[str] = None
    username: Optional[str] = None


class RunExamplesRequest(BaseModel):
    code: str
    examples: str
    slug: Optional[str] = None
    expected_outputs: list[str] | None = None
    public_cases_count: int | None = None
    order_independent: bool = False
    username: Optional[str] = None
    session_id: Optional[str] = None


class RunExamplesResponse(BaseModel):
    results: list[TestResult]
    stderr: str


class AnalyzeSubmissionRequest(BaseModel):
    code: str
    slug: str
    results: list[dict]
    stderr: str = ""
    level: int = 1
    username: Optional[str] = None
    session_id: Optional[str] = None


class ValidateSolutionRequest(BaseModel):
    title: str
    description: str
    constraints: str
    code: str
