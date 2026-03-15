from typing import Any

from pydantic import BaseModel


class TTSRequest(BaseModel):
    text: str


class VoiceRequest(BaseModel):
    session_id: str | None = "default-session"
    username: str | None = "anonymous"
    audio_chunk: str | None = None  # Base64 encoded audio
    code_context: str | None = None
    skill_id: str | None = "aries-default"


class VoiceResponse(BaseModel):
    text: str
    audio_chunk: str | None = None
    action: str | None = None
    action_payload: Any | None = None
    is_final: bool | None = None
    speech_final: bool | None = None


class SkillDefinition(BaseModel):
    name: str
    id: str
    persona: str
    prompt_extension: str
    triggers: list[str]
    supported_actions: list[str]
