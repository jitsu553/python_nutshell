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