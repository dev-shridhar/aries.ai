from pydantic import BaseModel
from typing import List, Optional, Any


class TTSRequest(BaseModel):
    text: str


class VoiceRequest(BaseModel):
    session_id: Optional[str] = "default-session"
    username: Optional[str] = "anonymous"
    audio_chunk: Optional[str] = None  # Base64 encoded audio
    code_context: Optional[str] = None
    skill_id: Optional[str] = "aries-default"


class VoiceResponse(BaseModel):
    text: str
    audio_chunk: Optional[str] = None
    action: Optional[str] = None
    action_payload: Optional[Any] = None


class SkillDefinition(BaseModel):
    name: str
    id: str
    persona: str
    prompt_extension: str
    triggers: List[str]
    supported_actions: List[str]
