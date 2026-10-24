from uuid import UUID
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: UUID
    user_id: UUID
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    index_status: str | None = None

    model_config = {"from_attributes": True}


class DeleteDocumentResponse(BaseModel):
    id: UUID
    deleted: bool


class DocumentListParams(BaseModel):
    page: int = 1
    page_size: int = 20
    content_type: str | None = None
    status: str | None = None  # index status: pending/processing/done/failed/dead
    q: str | None = None  # case-insensitive match on extracted text
    sort_by: Literal["created_at", "original_name", "size_bytes"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"


class DocumentListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    results: list[DocumentResponse]


class ReindexRequest(BaseModel):
    document_ids: list[UUID] = Field(min_length=1, max_length=1000)


class ReindexResponse(BaseModel):
    queued: list[int]
    already_queued: list[int]  # skipped: a job for these is already waiting in the queue
    processing: list[int]  # skipped: being indexed right now, retry once done
