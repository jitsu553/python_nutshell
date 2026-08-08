from datetime import datetime
from pydantic import BaseModel, Field

class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    system_prompt: str | None = Field(default=None, max_length=2000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=4096)

class PromptResponse(BaseModel):
    model: str
    prompt: str
    reply: str
    finish_reason: str | None = None

class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    system_prompt: str | None = Field(default=None, max_length=2000)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=4096)

class SessionResponse(BaseModel):
    id: int
    title: str | None
    system_prompt: str | None
    temperature: float | None
    max_tokens: int | None
    created_at: datetime

    model_config = {"from_attributes": True}

class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    stream: bool = False    


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    finish_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}