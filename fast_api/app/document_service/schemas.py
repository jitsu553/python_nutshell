from datetime import datetime

from pydantic import BaseModel, Field
from typing import Literal


class DocumentResponse(BaseModel):
    id: int
    user_id: int
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DeleteDocumentResponse(BaseModel):
    id: int
    deleted: bool

class RestoreDocumentResponse(BaseModel):
    id: int
    restored: bool  

class DocumentListParams(BaseModel):
    page: int = 1
    page_size: int = 20
    content_type: str | None = None
    sort_by: Literal["created_at", "original_name", "size_bytes"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"

    model_config = {"from_attributes": True}
    tag: str | None = None


class DocumentListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    results: list[DocumentResponse] 

class AddTagRequest(BaseModel):
    tag: str = Field(min_length=1, max_length=64)


class TagResponse(BaseModel):
    id: int
    document_id: int
    tag: str

    model_config = {"from_attributes": True}         