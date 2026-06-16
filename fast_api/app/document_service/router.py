from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, Request, Response, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.document_service.config import RETENTION_DAYS_SOFT_DELETED, STORAGE_BACKEND, S3_PRESIGNED_TTL_SECONDS, INDEX_QUEUE_BATCH_SIZE, INDEX_MAX_ATTEMPTS
from app.document_service.audit import audit_event
from app.auth.dependencies import get_current_user, get_db, require_role
from app.auth.models import User
from app.document_service.models import DocumentText
from app.document_service.schemas import (
    DeleteDocumentResponse,
    DocumentResponse,
    RestoreDocumentResponse,
    DocumentListParams,
    DocumentListResponse,
    AddTagRequest,
    TagResponse,
)
from app.document_service.service import DocumentService, run_index_document_task
from app.document_service.storage import LocalDocumentStorage
from app.document_service.storage_s3 import S3DocumentStorage
from app.document_service.extractor import extract_text
from app.redis_lab.rate_limit import rate_limit

router = APIRouter(prefix="/documents", tags=["documents"])

def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"

def get_storage_backend():
    if STORAGE_BACKEND == "local":
        return LocalDocumentStorage()
    if STORAGE_BACKEND == "s3":
        return S3DocumentStorage()
    raise RuntimeError(f"Unsupported storage backend: {STORAGE_BACKEND}")

def get_document_service(db: Session = Depends(get_db)) -> DocumentService:
    return DocumentService(db=db, storage=get_storage_backend())

    


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(limit=10, window_seconds=60, key_prefix="documents-upload"))],
)
def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    document = service.upload_document(file, current_user)
    # background_tasks.add_task(run_index_document_task, document.id)
    service.enqueue_index(document.id)
    audit_event(
        action="document.upload",
        user_id=current_user.id,
        document_id=document.id,
        ip=_client_ip(request),
        details={"filename": document.original_name, "size_bytes": document.size_bytes},
    )
    return document

@router.get("", response_model=list[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    return service.list_documents(current_user)

@router.get("/list", response_model=DocumentListResponse)
def list_documents_paginated(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    content_type: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    params = DocumentListParams(
        page=page,
        page_size=page_size,
        content_type=content_type,
        tag=tag,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return service.list_documents_paginated(current_user, params)

@router.get("/search/text")
def search_documents(
    request: Request,
    q: str,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    docs = service.search_indexed_documents(q, current_user)

    results = [
        {
            "id": doc.id,
            "original_name": doc.original_name,
            "content_type": doc.content_type,
            "size_bytes": doc.size_bytes,
        }
        for doc in docs
    ]

    audit_event(
        action="document.search",
        user_id=current_user.id,
        ip=_client_ip(request),
        details={"query": q, "matches": len(results)},
    )

    return {"query": q, "matches": len(results), "results": results}

@router.get(
    "/admin/all",
    response_model=list[DocumentResponse],
    dependencies=[Depends(require_role("admin"))],
)
def list_all_documents_admin(
    limit: int = 100,
    offset: int = 0,
    service: DocumentService = Depends(get_document_service),
):
    return service.list_documents_admin(limit=limit, offset=offset)

@router.post(
    "/admin/purge",
    dependencies=[Depends(require_role("admin"))],
)
def purge_soft_deleted_documents(
    retention_days: int = RETENTION_DAYS_SOFT_DELETED,
    service: DocumentService = Depends(get_document_service),
):
    result = service.purge_soft_deleted_older_than(retention_days=retention_days)
    return {"ok": True, **result}

@router.post(
    "/admin/index/process",
    dependencies=[Depends(require_role("admin"))],
)
def process_index_queue(
    batch_size: int = INDEX_QUEUE_BATCH_SIZE,
    max_attempts: int = INDEX_MAX_ATTEMPTS,
    service: DocumentService = Depends(get_document_service),
):
    result = service.process_pending_index_jobs(
        batch_size=batch_size,
        max_attempts=max_attempts,
    )
    return {"ok": True, **result}

@router.get(
    "/admin/index/dead",
    dependencies=[Depends(require_role("admin"))],
)
def list_dead_index_jobs(
    limit: int = 100,
    offset: int = 0,
    service: DocumentService = Depends(get_document_service),
):
    rows = service.list_dead_index_jobs(limit=limit, offset=offset)
    return {
        "count": len(rows),
        "results": [
            {
                "document_id": row.document_id,
                "status": row.status,
                "attempts": row.attempts,
                "last_error": row.last_error,
                "dead_at": row.dead_at,
            }
            for row in rows
        ],
    }

@router.post(
    "/admin/index/requeue/{document_id}",
    dependencies=[Depends(require_role("admin"))],
)
def requeue_dead_index_job(
    document_id: int,
    service: DocumentService = Depends(get_document_service),
):
    row = service.requeue_dead_job(document_id)
    return {
        "document_id": row.document_id,
        "status": row.status,
        "attempts": row.attempts,
        "requeued": True,
    }

@router.post(
    "/admin/restore/{document_id}",
    response_model=RestoreDocumentResponse,
    dependencies=[Depends(require_role("admin"))],
)
def restore_document_admin(
    document_id: int,
    service: DocumentService = Depends(get_document_service),
):
    document = service.restore_document_admin(document_id)
    return RestoreDocumentResponse(id=document.id, restored=True)

@router.delete(
    "/admin/{document_id}",
    response_model=DeleteDocumentResponse,
    dependencies=[Depends(require_role("admin"))],
)
def delete_document_admin(
    document_id: int,
    service: DocumentService = Depends(get_document_service),
):
    document = service.delete_document_admin(document_id)
    return DeleteDocumentResponse(id=document.id, deleted=True)

@router.post("/{document_id}/tags", response_model=TagResponse)
def add_document_tag(
    document_id: int,
    body: AddTagRequest,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    return service.add_tag(document_id=document_id, tag=body.tag, current_user=current_user)


@router.get("/{document_id}/tags", response_model=list[TagResponse])
def list_document_tags(
    document_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    return service.list_tags(document_id=document_id, current_user=current_user)


@router.delete("/{document_id}/tags/{tag}")
def remove_document_tag(
    document_id: int,
    tag: str,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    deleted = service.remove_tag(document_id=document_id, tag=tag, current_user=current_user)
    return {"document_id": document_id, "tag": tag, "deleted": deleted}

@router.get("/{document_id}/download-url")
def get_download_url(
    document_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    document = service.get_document_or_404(document_id, current_user)

    if STORAGE_BACKEND != "s3":
        return {
            "backend": STORAGE_BACKEND,
            "message": "Presigned URL is only available for s3 backend",
        }

    url = service.storage.generate_download_url(
        stored_name=document.stored_name,
        original_name=document.original_name,
        content_type=document.content_type,
        expires_in_seconds=S3_PRESIGNED_TTL_SECONDS,
    )
    return {
        "backend": "s3",
        "document_id": document.id,
        "expires_in_seconds": S3_PRESIGNED_TTL_SECONDS,
        "url": url,
    }

@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    document, file_path = service.get_document_download(document_id, current_user)

    etag = f"\"{document.sha256}\""
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    audit_event(
        action="document.download",
        user_id=current_user.id,
        document_id=document.id,
        ip=_client_ip(request),
    )
    response = FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.original_name,
    )
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=60"
    return response

@router.get("/{document_id}/preview")
def preview_document(
    request: Request,
    document_id: int,
    max_chars: int = 2000,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    document, text, source = service.get_or_index_text(document_id, current_user)
    audit_event(
        action="document.preview",
        user_id=current_user.id,
        document_id=document.id,
        ip=_client_ip(request),
        details={"max_chars": max_chars},
    )
    return {
        "id": document.id,
        "original_name": document.original_name,
        "content_type": document.content_type,
        "char_count": len(text),
        "source": source,
        "preview": text[:max_chars],
    }

@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    document = service.delete_document(document_id, current_user)
    audit_event(
        action="document.delete",
        user_id=current_user.id,
        document_id=document.id,
        ip=_client_ip(request),
    )
    return DeleteDocumentResponse(id=document.id, deleted=True)

@router.post("/index/{document_id}")
def index_document_text(
    document_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    entry = service.index_document_text(document_id, current_user)
    return {
        "document_id": document_id,
        "indexed": True,
        "char_count": len(entry.extracted_text),
        "indexed_at": entry.extracted_at,
    }

@router.get("/{document_id}/index-status")
def get_index_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    document = service.get_document_or_404(document_id, current_user)
    entry = (
        service.db.query(DocumentText)
        .filter(DocumentText.document_id == document.id)
        .first()
    )

    if not entry:
        return {"document_id": document.id, "status": "not-indexed"}

    return {
        "document_id": document.id,
        "status": entry.status,
        "attempts": entry.attempts,
        "last_error": entry.last_error,
        "char_count": len(entry.extracted_text or ""),
        "extracted_at": entry.extracted_at,
    }

@router.post("/{document_id}/reindex")
def reindex_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    service.get_document_or_404(document_id, current_user)
    service.enqueue_index(document_id)
    # background_tasks.add_task(run_index_document_task, document_id)
    return {"document_id": document_id, "queued": True}

