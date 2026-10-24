"""Background indexing: upload -> Redis queue -> extract text -> chunk -> embed -> pgvector.

Jobs are document ids on a Redis list; N asyncio workers per pod BLPOP them. Status lives
on DocumentText (pending -> processing -> done | failed -> retried | dead). Upload and
reindex both just enqueue, so they share one path.

Pod-safe: claiming is an atomic UPDATE, and every active row carries a deadline
(next_retry_at). A sweeper in each pod re-queues rows past their deadline, which covers
crashed pods, retry backoff and lost queue entries without in-memory timers.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta

from fastapi import FastAPI
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select, update

from app.core.config import get_settings
from app.infra.database import AsyncSessionLocal
from app.infra.redis_client import REDIS_APP_STATE_KEY
from app.models.documents import Document, DocumentText
from app.models.llm_chat import TextEmbedding
from app.services.documents.chunking import chunk_text
from app.services.documents.extractor import extract_text
from app.services.documents.storage import LocalDocumentStorage
from app.services.llm.client import EMBEDDINGS_APP_STATE_KEY

log = logging.getLogger(__name__)
settings = get_settings()

QUEUE_KEY = "documents:index:queue"
QUEUED_PREFIX = "documents:index:queued:"  # per-id marker so a document is queued at most once
EVENTS_CHANNEL = "documents:events"  # pub/sub: fire-and-forget status events, not jobs


async def enqueue(redis: Redis | None, document_ids: list[int]) -> list[int]:
    """Queue ids not already waiting in the queue; returns the ones actually added."""
    ids = list(dict.fromkeys(document_ids))
    if redis is None or not ids:
        return []
    try:
        # The marker expires after the lease, so a lost one can't block an id forever.
        added = await asyncio.gather(
            *(
                redis.set(f"{QUEUED_PREFIX}{i}", 1, nx=True, ex=settings.documents_index_lease_seconds)
                for i in ids
            )
        )
        new = [i for i, ok in zip(ids, added) if ok]
        if new:
            try:
                await redis.rpush(QUEUE_KEY, *new)
            except RedisError:
                await redis.delete(*(f"{QUEUED_PREFIX}{i}" for i in new))
                raise
        log.info("queued %d documents %s, %d already queued", len(new), new, len(ids) - len(new))
        return new
    except RedisError as exc:
        # Rows stay 'pending'; the sweeper re-queues them once their deadline passes.
        log.warning("could not enqueue documents %s: %s", ids, exc)
        return []


async def _publish(app: FastAPI, document_id: int, status: str, error: str | None = None) -> None:
    try:
        event = {"document_id": document_id, "status": status, "error": error}
        await getattr(app.state, REDIS_APP_STATE_KEY).publish(EVENTS_CHANNEL, json.dumps(event))
    except Exception:
        log.warning("could not publish event for document %s", document_id)


def _deadline(seconds: float) -> datetime:
    return datetime.utcnow() + timedelta(seconds=seconds)


async def _claim_and_extract(document_id: int) -> str | None:
    """Atomically claim a pending job (dupes on the queue are harmless) and extract text."""
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, document_id)
        if document is None or document.is_deleted:
            log.debug("document %s missing or deleted, skipping", document_id)
            return None
        result = await db.execute(
            update(DocumentText)
            .where(
                DocumentText.document_id == document_id,
                DocumentText.status == "pending",  # failed rows wait for the sweeper (backoff)
            )
            .values(
                status="processing",
                attempts=DocumentText.attempts + 1,
                last_error=None,
                next_retry_at=_deadline(settings.documents_index_lease_seconds),
            )
        )
        await db.commit()
        if not result.rowcount:
            log.debug("document %s not pending (already claimed or done), skipping", document_id)
            return None
        log.info("document %s claimed", document_id)
        # ponytail: local storage only; s3 backend would need a download-to-temp step here
        path = LocalDocumentStorage().build_path(document.stored_name)
        # pypdf / python-docx are blocking, so file checks and parsing run in a thread
        if not await asyncio.to_thread(path.exists):
            raise FileNotFoundError("Stored file not found")
        return await asyncio.to_thread(extract_text, path, document.content_type)


async def _save(document_id: int, text: str, chunks: list[str], vectors: list[list[float]]) -> None:
    async with AsyncSessionLocal() as db:
        document = await db.get(Document, document_id)
        await db.execute(delete(TextEmbedding).where(TextEmbedding.document_id == document_id))
        if document is not None and not document.is_deleted:  # may be deleted mid-job
            db.add_all(
                TextEmbedding(
                    document_id=document_id,
                    chunk_index=i,
                    source_text=chunk,
                    model=settings.llm_embedding_model,
                    embedding=vector,
                )
                for i, (chunk, vector) in enumerate(zip(chunks, vectors))
            )
        entry = await db.scalar(select(DocumentText).where(DocumentText.document_id == document_id))
        entry.extracted_text = text
        entry.extracted_at = datetime.utcnow()
        entry.status = "done"
        entry.last_error = None
        entry.next_retry_at = None
        await db.commit()


async def _fail(document_id: int, error: str) -> float | None:
    """Record the failure; return the retry delay in seconds, or None once the job is dead."""
    async with AsyncSessionLocal() as db:
        entry = await db.scalar(select(DocumentText).where(DocumentText.document_id == document_id))
        if entry is None:
            return None
        entry.last_error = error[:1000]
        if entry.attempts >= settings.documents_index_max_attempts:
            entry.status = "dead"
            entry.next_retry_at = None
            delay = None
        else:
            entry.status = "failed"
            delay = settings.documents_index_retry_base_seconds * 2 ** (entry.attempts - 1)
            entry.next_retry_at = _deadline(delay)  # the sweeper re-queues it then
        await db.commit()
        return delay


async def _process(app: FastAPI, document_id: int) -> None:
    started = time.monotonic()
    try:
        text = await _claim_and_extract(document_id)
        if text is None:
            return
        chunks = chunk_text(text)
        vectors: list[list[float]] = []
        if chunks:
            embeddings = getattr(app.state, EMBEDDINGS_APP_STATE_KEY, None)
            if embeddings is None:
                raise RuntimeError("Embeddings client is not initialized")
            vectors = await embeddings.aembed_documents(chunks)
        await _save(document_id, text, chunks, vectors)
        log.info(
            "document %s indexed: %d chunks in %.1fs", document_id, len(chunks), time.monotonic() - started
        )
        await _publish(app, document_id, "done")
    except Exception as exc:
        log.exception("indexing document %s failed", document_id)
        delay = await _fail(document_id, str(exc))
        if delay is None:
            log.error("document %s is dead after %d attempts", document_id, settings.documents_index_max_attempts)
        else:
            log.warning("document %s failed, retry in %ss", document_id, delay)
        await _publish(app, document_id, "failed" if delay is not None else "dead", str(exc)[:200])


async def _worker(app: FastAPI) -> None:
    redis: Redis = getattr(app.state, REDIS_APP_STATE_KEY)
    while True:
        try:
            item = await redis.blpop(QUEUE_KEY, timeout=5)
            if item:
                document_id = int(item[1])
                await redis.delete(f"{QUEUED_PREFIX}{document_id}")  # may be queued again now
                await _process(app, document_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("index worker error")
            await asyncio.sleep(1)


async def _sweep() -> list[int]:
    """Re-queue active rows past their deadline (crashed pod, retry backoff, lost queue entry)."""
    # ponytail: a job slower than the lease may run twice; raise documents_index_lease_seconds
    async with AsyncSessionLocal() as db:
        rows = (
            await db.scalars(
                select(DocumentText)
                .join(Document, Document.id == DocumentText.document_id)
                .where(
                    Document.is_deleted.is_(False),
                    DocumentText.status.in_(("pending", "failed", "processing")),
                    DocumentText.next_retry_at <= datetime.utcnow(),
                )
                .with_for_update(skip_locked=True, of=DocumentText)  # one pod per row
            )
        ).all()
        ids, dead = [], []
        for row in rows:
            if row.attempts >= settings.documents_index_max_attempts:
                row.status = "dead"
                row.next_retry_at = None
                row.last_error = row.last_error or "lease expired"
                dead.append(row.document_id)
            else:
                row.status = "pending"
                row.next_retry_at = _deadline(settings.documents_index_lease_seconds)
                ids.append(row.document_id)
        await db.commit()
        if ids:
            log.info("sweeper re-queueing %s", ids)
        if dead:
            log.warning("sweeper marked dead %s", dead)
        return ids


async def _sweeper(app: FastAPI) -> None:
    redis = getattr(app.state, REDIS_APP_STATE_KEY)
    while True:
        try:
            await enqueue(redis, await _sweep())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("index sweeper error")
        await asyncio.sleep(settings.documents_index_sweep_seconds)


async def start_workers(app: FastAPI) -> None:
    redis = getattr(app.state, REDIS_APP_STATE_KEY, None)
    if redis is None:
        log.warning("Redis unavailable: document indexing workers not started")
        return
    app.state.index_workers = [
        asyncio.create_task(_worker(app)) for _ in range(settings.documents_index_workers)
    ] + [asyncio.create_task(_sweeper(app))]
    log.info("started %d index workers + sweeper", settings.documents_index_workers)


async def stop_workers(app: FastAPI) -> None:
    tasks = getattr(app.state, "index_workers", [])
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    if tasks:
        log.info("stopped index workers + sweeper")
