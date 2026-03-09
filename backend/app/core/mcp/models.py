from pydantic import BaseModel


class ExplainRequest(BaseModel):
    title: str
    slug: str


class ExplainResponse(BaseModel):
    response: str


class SubmitRequest(BaseModel):
    code: str
    slug: str


class TutorIntroRequest(BaseModel):
    title: str
    slug: str
    content: str


class TutorAnalyzeRequest(BaseModel):
    code: str
    slug: str
    problem_title: str
    problem_description: str
    history: list[dict] = []
