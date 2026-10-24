import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import asc, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.auth import User
from app.models.documents import Document, DocumentText
from app.models.llm_chat import TextEmbedding
from app.schemas.documents import DocumentListParams
from app.services.documents.storage_backend import DocumentStorageBackend

settings = get_settings()
log = logging.getLogger(__name__)


class DocumentService:
    def __init__(self, db: AsyncSession, storage: DocumentStorageBackend):
        self.db = db
        self.storage = storage

    async def upload_documents(self, uploads: list[UploadFile], current_user: User) -> list[Document]:
        """Store every file (no dedup) with a pending index row. All-or-nothing per batch."""
        stored = []
        try:
            documents = []
            for upload in uploads:
                # storage is plain file I/O (no async form), so it runs in a thread
                f = await asyncio.to_thread(self.storage.save, upload)
                stored.append(f)
                documents.append(
                    Document(
                        user_id=current_user.id,
                        original_name=f.original_name,
                        stored_name=f.stored_name,
                        content_type=f.content_type,
                        size_bytes=f.size_bytes,
                        sha256=f.sha256,
                        text_entry=DocumentText(status="pending", next_retry_at=self._lease_deadline()),
                    )
                )
            self.db.add_all(documents)
            await self.db.commit()  # ids are set; nothing expires, so no refresh needed
            log.info("uploaded %d documents by user %s: %s", len(documents), current_user.id, [d.id for d in documents])
            return documents
        except Exception:
            await self.db.rollback()
            for f in stored:
                await asyncio.to_thread(self.storage.delete, f.stored_name)
            raise

    @staticmethod
    def _lease_deadline() -> datetime:
        return datetime.utcnow() + timedelta(seconds=settings.documents_index_lease_seconds)

    async def list_documents(self, params: DocumentListParams) -> dict:
        page_size = min(max(params.page_size, 1), 100)
        page = max(params.page, 1)

        filters = [Document.is_deleted.is_(False)]
        if params.content_type:
            filters.append(Document.content_type == params.content_type)
        if params.status:
            filters.append(DocumentText.status == params.status)
        if params.q:
            escaped = params.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append(DocumentText.extracted_text.ilike(f"%{escaped}%", escape="\\"))

        joined = Document.id == DocumentText.document_id
        total = await self.db.scalar(
            select(func.count(Document.id)).join(DocumentText, joined).where(*filters)
        ) or 0

        order_fn = asc if params.sort_order == "asc" else desc
        results = (
            await self.db.scalars(
                select(Document)
                .join(DocumentText, joined)
                .options(selectinload(Document.text_entry))
                .where(*filters)
                .order_by(order_fn(getattr(Document, params.sort_by)), Document.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return {"page": page, "page_size": page_size, "total": total, "results": results}

    async def delete_document(self, document_id: int, current_user: User) -> Document:
        """Soft delete; any user may delete any document."""
        document = await self.db.scalar(
            select(Document)
            .options(selectinload(Document.text_entry))
            .where(Document.id == document_id, Document.is_deleted.is_(False))
        )
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        document.is_deleted = True
        document.deleted_at = datetime.now(timezone.utc)
        document.deleted_by_user_id = current_user.id
        # Keep deleted content out of semantic search / RAG.
        await self.db.execute(delete(TextEmbedding).where(TextEmbedding.document_id == document_id))
        await self.db.commit()
        log.info("document %s soft-deleted by user %s", document_id, current_user.id)
        return document

    async def reset_for_reindex(self, document_ids: list[int]) -> tuple[list[int], list[int]]:
        """Mark the given documents pending again (even if done).
        Returns (ids to enqueue, ids skipped because a job is running right now)."""
        entries = (
            await self.db.scalars(
                select(DocumentText)
                .join(Document, Document.id == DocumentText.document_id)
                .where(Document.is_deleted.is_(False), DocumentText.document_id.in_(document_ids))
            )
        ).all()
        missing = set(document_ids) - {e.document_id for e in entries}
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documents not found: {sorted(missing)}",
            )

        # An expired lease means the worker died, so that row can be taken over.
        now = datetime.utcnow()
        running = [
            e.document_id
            for e in entries
            if e.status == "processing" and e.next_retry_at and e.next_retry_at > now
        ]
        entries = [e for e in entries if e.document_id not in running]
        taken_over = [e.document_id for e in entries if e.status == "processing"]
        if taken_over:
            log.warning("reindex taking over expired processing rows %s", taken_over)
        for entry in entries:
            entry.status = "pending"
            entry.attempts = 0
            entry.last_error = None
            entry.next_retry_at = self._lease_deadline()
        await self.db.commit()
        log.info("reindex reset %s, skipped running %s", [e.document_id for e in entries], running)
        return [e.document_id for e in entries], running
