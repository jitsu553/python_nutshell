import logging

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.infra.rate_limit import rate_limit
from app.infra.redis_client import get_optional_redis
from app.models.auth import User
from app.schemas.documents import (
    DeleteDocumentResponse,
    DocumentListParams,
    DocumentListResponse,
    DocumentResponse,
    ReindexRequest,
    ReindexResponse,
)
from app.services.documents.audit import audit_event
from app.services.documents.indexer import enqueue
from app.services.documents.service import DocumentService
from app.services.documents.storage import LocalDocumentStorage
from app.services.documents.storage_s3 import S3DocumentStorage

settings = get_settings()
log = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def get_storage_backend():
    if settings.documents_storage_backend == "local":
        return LocalDocumentStorage()
    if settings.documents_storage_backend == "s3":
        return S3DocumentStorage()
    raise RuntimeError(f"Unsupported storage backend: {settings.documents_storage_backend}")


def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    return DocumentService(db=db, storage=get_storage_backend())


@router.post(
    "/upload",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(limit=10, window_seconds=60, key_prefix="documents-upload"))],
)
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
    redis: Redis | None = Depends(get_optional_redis),
):
    """One or many files. Each is stored and queued for extraction + embedding."""
    documents = await service.upload_documents(files, current_user)
    await enqueue(redis, [d.id for d in documents])
    for document in documents:
        audit_event(
            action="document.upload",
            user_id=current_user.id,
            document_id=document.id,
            ip=_client_ip(request),
            details={"filename": document.original_name, "size_bytes": document.size_bytes},
        )
    return documents


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    content_type: str | None = None,
    status: str | None = Query(default=None, description="pending/processing/done/failed/dead"),
    q: str | None = Query(default=None, description="text search in extracted content"),
    sort_by: str = "created_at",
    sort_order: str = "desc",
    _: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    params = DocumentListParams(
        page=page,
        page_size=page_size,
        content_type=content_type,
        status=status,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await service.list_documents(params)


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    document = await service.delete_document(document_id, current_user)
    audit_event(
        action="document.delete",
        user_id=current_user.id,
        document_id=document.id,
        ip=_client_ip(request),
    )
    return DeleteDocumentResponse(id=document.id, deleted=True)


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_documents(
    body: ReindexRequest,
    _: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
    redis: Redis | None = Depends(get_optional_redis),
):
    """Re-run extraction + embedding from scratch for the given documents, even if done.
    Documents already waiting in the queue, or being processed right now, are skipped."""
    ids, processing = await service.reset_for_reindex(body.document_ids)
    queued = await enqueue(redis, ids)
    already_queued = [i for i in ids if i not in queued]
    log.info(
        "reindex requested for %d documents: queued=%s already_queued=%s processing=%s",
        len(body.document_ids), queued, already_queued, processing,
    )
    return ReindexResponse(queued=queued, already_queued=already_queued, processing=processing)
