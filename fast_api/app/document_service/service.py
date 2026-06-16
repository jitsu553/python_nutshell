from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc, desc, func

from app.db import SessionLocal
from app.auth.models import User
from app.document_service.models import Document
from app.document_service.storage import LocalDocumentStorage
from app.document_service.storage_backend import DocumentStorageBackend
from app.document_service.extractor import extract_text
from app.document_service.models import Document, DocumentTag, DocumentText
from app.document_service.config import (
    INDEX_DEAD_STATUS,
    INDEX_MAX_ATTEMPTS,
    INDEX_RETRY_BASE_SECONDS,
    INDEX_RETRY_MAX_SECONDS,
)
from app.document_service.schemas import DocumentListParams



class DocumentService:
    def __init__(self, db: Session, storage: DocumentStorageBackend):
        self.db = db
        self.storage = storage

    def upload_document(self, upload: UploadFile, current_user: User) -> Document:
        stored_file = self.storage.save(upload)

        try:
            # Idempotent behavior: if same user uploads same file content again,
            # return existing metadata and remove newly written duplicate blob.
            existing = (
                self.db.query(Document)
                .filter(
                    Document.user_id == current_user.id,
                    Document.sha256 == stored_file.sha256,
                    Document.size_bytes == stored_file.size_bytes,
                    Document.content_type == stored_file.content_type,
                )
                .first()
            )
            if existing:
                self.storage.delete(stored_file.stored_name)
                return existing

            document = Document(
                user_id=current_user.id,
                original_name=stored_file.original_name,
                stored_name=stored_file.stored_name,
                content_type=stored_file.content_type,
                size_bytes=stored_file.size_bytes,
                sha256=stored_file.sha256,
            )

            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)
            return document

        except Exception:
            self.db.rollback()
            self.storage.delete(stored_file.stored_name)
            raise

    def list_documents(self, current_user: User) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(
                Document.user_id == current_user.id,
                Document.is_deleted.is_(False),
            )
            .order_by(Document.created_at.desc())
            .all()
        )

    def get_document_or_404(self, document_id: int, current_user: User) -> Document:
        document = (
            self.db.query(Document)
            .filter(
                Document.id == document_id,
                Document.user_id == current_user.id,
                Document.is_deleted.is_(False),
            )
            .first()
        )

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        return document

    def get_document_download(self, document_id: int, current_user: User) -> tuple[Document, Path]:
        document = self.get_document_or_404(document_id, current_user)
        file_path = self.storage.build_path(document.stored_name)

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored file not found",
            )

        return document, file_path

    def delete_document(self, document_id: int, current_user: User) -> Document:
        document = (
            self.db.query(Document)
            .filter(
                Document.id == document_id,
                Document.user_id == current_user.id,
                Document.is_deleted.is_(False),
            )
            .first()
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        document.is_deleted = True
        document.deleted_at = datetime.now(timezone.utc)
        document.deleted_by_user_id = current_user.id
        self.db.commit()
        self.db.refresh(document)
        return document

    def restore_document_admin(self, document_id: int) -> Document:
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        document.is_deleted = False
        document.deleted_at = None
        document.deleted_by_user_id = None
        self.db.commit()
        self.db.refresh(document)
        return document

    def index_document_text(self, document_id: int, current_user: User) -> DocumentText:
        document = self.get_document_or_404(document_id, current_user)
        file_path = self.storage.build_path(document.stored_name)

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored file not found",
            )

        text = extract_text(file_path, document.content_type)

        entry = (
            self.db.query(DocumentText)
            .filter(DocumentText.document_id == document.id)
            .first()
        )

        if entry is None:
            entry = DocumentText(
                document_id=document.id,
                extracted_text=text,
                extracted_at=datetime.utcnow(),
            )
            self.db.add(entry)
        else:
            entry.extracted_text = text
            entry.extracted_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_or_index_text(self, document_id: int, current_user: User) -> tuple[Document, str, str]:
        document = self.get_document_or_404(document_id, current_user)

        entry = (
            self.db.query(DocumentText)
            .filter(DocumentText.document_id == document.id)
            .first()
        )
        if entry is not None:
            return document, entry.extracted_text, "cached"

        entry = self.index_document_text(document_id, current_user)
        return document, entry.extracted_text, "indexed"

    def search_indexed_documents(self, q: str, current_user: User) -> list[Document]:
        return (
            self.db.query(Document)
            .join(DocumentText, DocumentText.document_id == Document.id)
            .options(joinedload(Document.text_entry))
            .filter(
                Document.user_id == current_user.id,
                DocumentText.extracted_text.ilike(f"%{q}%"),
            )
            .order_by(Document.created_at.desc())
            .all()
        )

    def list_documents_admin(self, limit: int = 100, offset: int = 0) -> list[Document]:
        limit = min(max(limit, 1), 500)
        offset = max(offset, 0)

        return (
            self.db.query(Document)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def delete_document_admin(self, document_id: int) -> Document:
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        stored_name = document.stored_name
        self.db.delete(document)
        self.db.commit()
        self.storage.delete(stored_name)
        return document

    def purge_soft_deleted_older_than(self, retention_days: int) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        targets = (
            self.db.query(Document)
            .filter(
                Document.is_deleted.is_(True),
                Document.deleted_at.is_not(None),
                Document.deleted_at < cutoff,
            )
            .all()
        )

        purged_count = 0
        failed_count = 0

        for doc in targets:
            try:
                stored_name = doc.stored_name

                # Remove DB row first (authoritative record).
                self.db.delete(doc)
                self.db.flush()

                # Best-effort delete file blob.
                self.storage.delete(stored_name)

                purged_count += 1
            except Exception:
                failed_count += 1

        self.db.commit()

        return {
            "retention_days": retention_days,
            "eligible": len(targets),
            "purged": purged_count,
            "failed": failed_count,
        }

    def enqueue_index(self, document_id: int) -> None:
        entry = (
            self.db.query(DocumentText)
            .filter(DocumentText.document_id == document_id)
            .first()
        )
        if entry is None:
            entry = DocumentText(
                document_id=document_id,
                extracted_text="",
                status="pending",
                attempts=0,
                last_error=None,
            )
            self.db.add(entry)
        else:
            # Re-queue only if not currently processing.
            if entry.status != "processing":
                entry.status = "pending"
                entry.last_error = None

        self.db.commit()

    def process_pending_index_jobs(
        self,
        *,
        batch_size: int,
        max_attempts: int,
    ) -> dict:
        entries = self.claim_pending_index_jobs(
            batch_size=batch_size,
            max_attempts=max_attempts,
        )

        processed = 0
        succeeded = 0
        failed = 0

        for entry in entries:
            processed += 1
            # entry.status = "processing"
            # entry.attempts += 1
            # entry.last_error = None
            # self.db.commit()

            try:
                document = (
                    self.db.query(Document)
                    .filter(Document.id == entry.document_id)
                    .first()
                )
                if document is None:
                    self._mark_failed_with_backoff(entry, "document not found")
                    failed += 1
                    continue

                file_path = self.storage.build_path(document.stored_name)
                if not file_path.exists():
                    self._mark_failed_with_backoff(entry, "stored file not found")
                    failed += 1
                    continue

                text = extract_text(file_path, document.content_type)
                entry.extracted_text = text
                entry.extracted_at = datetime.utcnow()
                entry.status = "done"
                entry.last_error = None
                succeeded += 1
                self.db.commit()

            except Exception as exc:
                self.db.rollback()
                refreshed = (
                    self.db.query(DocumentText)
                    .filter(DocumentText.id == entry.id)
                    .first()
                )
                if refreshed:
                    self._mark_failed_with_backoff(refreshed, str(exc))
                failed += 1

        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "batch_size": batch_size,
            "max_attempts": max_attempts,
            "claimed_job_ids": [entry.id for entry in entries],
        }
    
    def claim_pending_index_jobs(
        self,
        *,
        batch_size: int,
        max_attempts: int,
    ) -> list[DocumentText]:
        now = datetime.now(timezone.utc)

        jobs = (
            self.db.query(DocumentText)
            .filter(
                DocumentText.status.in_(["pending", "failed"]),
                DocumentText.attempts < max_attempts,
                (
                    (DocumentText.next_retry_at.is_(None)) |
                    (DocumentText.next_retry_at <= now)
                ),
            )
            .order_by(DocumentText.id.asc())
            .with_for_update(skip_locked=True)
            .limit(batch_size)
            .all()
        )

        for job in jobs:
            job.status = "processing"
            job.attempts += 1
            job.last_error = None
            job.next_retry_at = None

        self.db.commit()
        return jobs
    
    def _compute_backoff_seconds(self, attempts: int) -> int:
        seconds = INDEX_RETRY_BASE_SECONDS * (2 ** max(attempts - 1, 0))
        return min(seconds, INDEX_RETRY_MAX_SECONDS)

    def _mark_failed_with_backoff(self, entry: DocumentText, error_text: str) -> None:
        now = datetime.now(timezone.utc)

        if entry.attempts >= INDEX_MAX_ATTEMPTS:
            entry.status = INDEX_DEAD_STATUS
            entry.dead_at = now
            entry.last_error = error_text[:1000]
            entry.next_retry_at = None
            self.db.commit()
            return

        wait_seconds = self._compute_backoff_seconds(entry.attempts)
        entry.status = "failed"
        entry.last_error = error_text[:1000]
        entry.next_retry_at = now + timedelta(seconds=wait_seconds)
        self.db.commit()    

    def list_dead_index_jobs(self, limit: int = 100, offset: int = 0) -> list[DocumentText]:
        limit = min(max(limit, 1), 500)
        offset = max(offset, 0)

        return (
            self.db.query(DocumentText)
            .filter(DocumentText.status == INDEX_DEAD_STATUS)
            .order_by(DocumentText.dead_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def requeue_dead_job(self, document_id: int) -> DocumentText:
        entry = (
            self.db.query(DocumentText)
            .filter(DocumentText.document_id == document_id)
            .first()
        )
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Index job not found",
            )

        entry.status = "pending"
        entry.last_error = None
        entry.next_retry_at = None
        entry.dead_at = None
        entry.attempts = 0

        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_documents_paginated(
        self,
        current_user: User,
        params: DocumentListParams,
    ) -> dict:
        page_size = min(max(params.page_size, 1), 100)
        page = max(params.page, 1)
        offset = (page - 1) * page_size

        query = self.db.query(Document).filter(
            Document.user_id == current_user.id,
            Document.is_deleted.is_(False),
        )

        if params.content_type:
            query = query.filter(Document.content_type == params.content_type)

        if getattr(params, "tag", None):
            query = query.join(DocumentTag, DocumentTag.document_id == Document.id).filter(
                DocumentTag.tag == params.tag.strip().lower()
            )

        total = query.with_entities(func.count(Document.id)).scalar() or 0

        sort_col = getattr(Document, params.sort_by)
        order_fn = asc if params.sort_order == "asc" else desc
        query = query.order_by(order_fn(sort_col))

        results = query.offset(offset).limit(page_size).all()

        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "results": results,
        }

    def add_tag(self, document_id: int, tag: str, current_user: User) -> DocumentTag:
        document = self.get_document_or_404(document_id, current_user)
        normalized = tag.strip().lower()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tag cannot be empty",
            )

        existing = (
            self.db.query(DocumentTag)
            .filter(
                DocumentTag.document_id == document.id,
                DocumentTag.tag == normalized,
            )
            .first()
        )
        if existing:
            return existing

        row = DocumentTag(document_id=document.id, tag=normalized)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_tags(self, document_id: int, current_user: User) -> list[DocumentTag]:
        document = self.get_document_or_404(document_id, current_user)
        return (
            self.db.query(DocumentTag)
            .filter(DocumentTag.document_id == document.id)
            .order_by(DocumentTag.tag.asc())
            .all()
        )

    def remove_tag(self, document_id: int, tag: str, current_user: User) -> bool:
        document = self.get_document_or_404(document_id, current_user)
        normalized = tag.strip().lower()

        row = (
            self.db.query(DocumentTag)
            .filter(
                DocumentTag.document_id == document.id,
                DocumentTag.tag == normalized,
            )
            .first()
        )
        if row is None:
            return False

        self.db.delete(row)
        self.db.commit()
        return True


        

def run_index_document_task(document_id: int) -> None:
    """
    Background-safe index task with explicit status lifecycle:
    pending -> processing -> done / failed
    """
    db = SessionLocal()
    storage = LocalDocumentStorage()

    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None:
            return

        # Find or create index row
        entry = (
            db.query(DocumentText)
            .filter(DocumentText.document_id == document.id)
            .first()
        )
        if entry is None:
            entry = DocumentText(
                document_id=document.id,
                extracted_text="",
                status="pending",
                attempts=0,
                last_error=None,
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)

        # Mark processing + increment attempts
        entry.status = "processing"
        entry.attempts = (entry.attempts or 0) + 1
        entry.last_error = None
        db.commit()

        # Validate source file presence
        file_path = storage.build_path(document.stored_name)
        if not file_path.exists():
            entry.status = "failed"
            entry.last_error = "Stored file not found"
            db.commit()
            return

        # Extract and persist
        text = extract_text(file_path, document.content_type)
        entry.extracted_text = text
        entry.extracted_at = datetime.utcnow()
        entry.status = "done"
        entry.last_error = None
        db.commit()

    except Exception as exc:
        db.rollback()

        # Best-effort failure status update
        try:
            entry = (
                db.query(DocumentText)
                .filter(DocumentText.document_id == document_id)
                .first()
            )
            if entry:
                entry.status = "failed"
                entry.last_error = str(exc)[:1000]
                entry.attempts = max(entry.attempts or 0, 1)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()

