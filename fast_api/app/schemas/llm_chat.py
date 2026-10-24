from uuid import UUID
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
    use_rag: bool = False
    rag_document_id: UUID | None = None
    use_tools: bool = False

class SessionResponse(BaseModel):
    id: UUID
    title: str | None
    system_prompt: str | None
    temperature: float | None
    max_tokens: int | None
    use_rag: bool
    rag_document_id: UUID | None
    created_at: datetime
    use_tools: bool

    model_config = {"from_attributes": True}

class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    stream: bool = False    


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    finish_reason: str | None
    created_at: datetime
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    model_config = {"from_attributes": True}

class EmbedRequest(BaseModel):
    input: str | list[str]

class EmbedResponse(BaseModel):
    model: str
    embeddings: list[list[float]]
    dimensions: int

class SimilarityRequest(BaseModel):
    text_a: str = Field(min_length=1)
    text_b: str = Field(min_length=1)

class SimilarityResponse(BaseModel):
    text_a: str
    text_b: str
    similarity: float 

class IngestResponse(BaseModel):
    stored_ids: list[UUID]

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)

class SearchResult(BaseModel):
    id: UUID
    text: str
    similarity: float
    document_id: UUID | None = None
    chunk_index: int | None = None

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]

class RagAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
    document_id: UUID | None = None
    min_similarity: float | None = Field(default=None, ge=0.0, le=1.0)


class RagSource(BaseModel):
    document_id: UUID | None
    chunk_index: int | None
    similarity: float
    text: str


class RagAskResponse(BaseModel):
    question: str
    answer: str
    sources: list[RagSource]

class PendingApprovalResponse(BaseModel):
    id: UUID
    session_id: UUID
    tool_name: str
    tool_args: dict
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}

class ApprovalDecisionRequest(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=500)

