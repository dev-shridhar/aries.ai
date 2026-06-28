from typing import Any, Optional
from pydantic import BaseModel


class VoiceResponse(BaseModel):
    text: str
    audio_chunk: Optional[str] = None
    action: Optional[str] = None
    action_payload: Optional[Any] = None


class RunCodeRequest(BaseModel):
    code: str
    stdin: str = ""
    session_id: str = ""


class RunCodeResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
