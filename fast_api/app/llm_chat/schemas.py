from pydantic import BaseModel, Field


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


class PromptResponse(BaseModel):
    model: str
    prompt: str
    reply: str