"""Request and response models for the MCP (Model Context Protocol) slice.

This module defines the Pydantic models used to orchestrate tool-calling
and platform metadata retrieval from LeetCode.
"""

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    """Payload to request an AI explanation for a specific problem."""

    title: str = Field(..., description="The readable title of the problem.")
    slug: str = Field(..., description="The URL-friendly identifier (slug).")


class ExplainResponse(BaseModel):
    """Result of an AI-generated problem explanation."""

    response: str = Field(..., description="The generated explanation content.")


class SubmitRequest(BaseModel):
    """Payload for full problem submission and evaluation."""

    code: str = Field(..., description="The user's solution code.")
    slug: str = Field(..., description="The problem slug.")
    username: str | None = Field(None, description="Platform handle.")
    session_id: str | None = Field(None, description="Active session ID.")


class TutorIntroRequest(BaseModel):
    """Payload to initialize a tutoring session for a problem."""

    title: str = Field(..., description="Problem title.")
    slug: str = Field(..., description="Problem slug.")
    content: str = Field(..., description="Full problem content/description.")


class TutorAnalyzeRequest(BaseModel):
    """Payload for ongoing AI tutoring analysis of user code."""

    code: str = Field(..., description="Current user code.")
    slug: str = Field(..., description="Problem slug.")
    problem_title: str = Field(..., description="Problem title.")
    problem_description: str = Field(..., description="Problem markdown content.")
    history: list[dict] = Field(
        default_factory=list, description="Interaction history."
    )
    username: str | None = None
    session_id: str | None = None
