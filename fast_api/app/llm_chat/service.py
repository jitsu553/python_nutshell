
from fastapi import HTTPException
from sqlalchemy.orm import Session
import httpx
import json

from .config import get_llm_settings
from .models import ChatMessage, ChatSession, TextEmbedding
from .schemas import CreateSessionRequest, PromptRequest, EmbedRequest, EmbedResponse
from app.db import SessionLocal
from app.document_service.service import DocumentService
from app.document_service.storage import LocalDocumentStorage
from app.auth.models import User
from .utils.chunking import chunk_text

RAG_SYSTEM_PROMPT = (
    "Answer the question using only the context below. "
    "If the context doesn't contain the answer, say you don't know — do not guess."
)


def build_messages(body: PromptRequest) -> list[dict]:
    messages = []
    if body.system_prompt:
        messages.append({"role": "system", "content": body.system_prompt})
    messages.append({"role": "user", "content": body.prompt})
    return messages


def build_payload(body: PromptRequest, *, stream: bool = False) -> dict:
    settings = get_llm_settings()

    payload = {
        "model": settings.llm_model,
        "messages": build_messages(body),
    }
    if body.temperature is not None:
        payload["temperature"] = body.temperature
    if body.max_tokens is not None:
        payload["max_tokens"] = body.max_tokens
    if stream:
        payload["stream"] = True

    return payload

async def embed_texts(body: EmbedRequest, client: httpx.AsyncClient) -> EmbedResponse:
    settings = get_llm_settings()

    texts = body.input if isinstance(body.input, list) else [body.input]
    if not texts or any(not t.strip() for t in texts):
        raise HTTPException(status_code=422, detail="input must contain non-empty text")

    payload = {
        "model": settings.llm_embedding_model,
        "input": texts,
    }

    try:
        response = await client.post("/embeddings", json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Embedding request failed: {exc.response.text}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach LLM server: {exc}")

    data = response.json()
    # print(data)
    sorted_items = sorted(data["data"], key=lambda item: item["index"])
    vectors = [item["embedding"] for item in sorted_items]

    return EmbedResponse(
        model=settings.llm_embedding_model,
        embeddings=vectors,
        dimensions=len(vectors[0]) if vectors else 0,
    )

def store_embedding(
    db: Session,
    text: str,
    vector: list[float],
    model: str,
    document_id: int | None = None,
    chunk_index: int | None = None,
) -> TextEmbedding:
    row = TextEmbedding(
        source_text=text,
        model=model,
        embedding=vector,
        document_id=document_id,
        chunk_index=chunk_index,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def find_similar(
    db: Session,
    query_vector: list[float],
    limit: int = 5,
    document_id: int | None = None,
) -> list[tuple[TextEmbedding, float]]:
    distance_expr = TextEmbedding.embedding.cosine_distance(query_vector)
    query = db.query(TextEmbedding, distance_expr)
    if document_id is not None:
        query = query.filter(TextEmbedding.document_id == document_id)
    rows = query.order_by(distance_expr).limit(limit).all()
    return [(row_embedding, 1 - distance) for row_embedding, distance in rows]

async def index_document_chunks(
    db: Session,
    document_id: int,
    current_user: User,
    client: httpx.AsyncClient,
) -> list[TextEmbedding]:
    doc_service = DocumentService(db=db, storage=LocalDocumentStorage())
    document, text, _source = doc_service.get_or_index_text(document_id, current_user)

    chunks = chunk_text(text)
    if not chunks:
        return []

    embed_result = await embed_texts(EmbedRequest(input=chunks), client)

    return [
        store_embedding(db, chunk, vector, embed_result.model, document_id=document.id, chunk_index=index)
        for index, (chunk, vector) in enumerate(zip(chunks, embed_result.embeddings))
    ]

def build_rag_context(chunks: list[TextEmbedding]) -> str:
    return "\n\n".join(f"[{i + 1}] {chunk.source_text}" for i, chunk in enumerate(chunks))


async def answer_with_context(question: str, chunks: list[TextEmbedding], client: httpx.AsyncClient) -> str:
    settings = get_llm_settings()
    context = build_rag_context(chunks)
    print(context)

    messages = [
        {"role": "system", "content": f"{RAG_SYSTEM_PROMPT}\n\nContext:\n{context}"},
        {"role": "user", "content": question},
    ]
    payload = {"model": settings.llm_model, "messages": messages}

    try:
        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc.response.text}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach LLM server: {exc}")

    data = response.json()
    return data["choices"][0]["message"]["content"]

class ChatService:
    def __init__(self, db: Session, client: httpx.AsyncClient):
        self.db = db
        self.client = client

    def create_session(self, body: CreateSessionRequest) -> ChatSession:
        session = ChatSession(
            title=body.title,
            system_prompt=body.system_prompt,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session_or_404(self, session_id: int) -> ChatSession:
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session is None:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session

    def list_messages(self, session_id: int) -> list[ChatMessage]:
        session = self.get_session_or_404(session_id)
        return session.messages

    async def send_message(self, session_id: int, content: str) -> ChatMessage:
        session = self.get_session_or_404(session_id)
        settings = get_llm_settings()

        user_message = ChatMessage(session_id=session.id, role="user", content=content)
        self.db.add(user_message)
        self.db.commit()

        history = [{"role": m.role, "content": m.content} for m in session.messages]

        messages = []
        if session.system_prompt:
            messages.append({"role": "system", "content": session.system_prompt})
        messages.extend(history)

        payload = {
            "model": settings.llm_model,
            "messages": messages,
        }
        if session.temperature is not None:
            payload["temperature"] = session.temperature
        if session.max_tokens is not None:
            payload["max_tokens"] = session.max_tokens

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"LLM request failed: {exc.response.text}")
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Could not reach LLM server: {exc}")

        data = response.json()
        choice = data["choices"][0]

        assistant_message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=choice["message"]["content"],
            finish_reason=choice.get("finish_reason"),
        )
        self.db.add(assistant_message)
        self.db.commit()
        self.db.refresh(assistant_message)
        return assistant_message

    async def send_message_stream(self, session_id: int, content: str):
        session = self.get_session_or_404(session_id)
        settings = get_llm_settings()

        user_message = ChatMessage(session_id=session.id, role="user", content=content)
        self.db.add(user_message)
        self.db.commit()

        history = [{"role": m.role, "content": m.content} for m in session.messages]

        messages = []
        if session.system_prompt:
            messages.append({"role": "system", "content": session.system_prompt})
        messages.extend(history)

        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": True,
        }
        if session.temperature is not None:
            payload["temperature"] = session.temperature
        if session.max_tokens is not None:
            payload["max_tokens"] = session.max_tokens

        session_id_captured = session.id

        async def token_generator():
            collected = ""
            finish_reason = None

            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    choice = chunk["choices"][0]
                    delta = choice["delta"].get("content")
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
                    if delta:
                        collected += delta
                        yield delta

            # EXPERIMENT: reusing self.db instead of a fresh SessionLocal()
            assistant_message = ChatMessage(
                session_id=session_id_captured,
                role="assistant",
                content=collected,
                finish_reason=finish_reason,
            )
            self.db.add(assistant_message)
            self.db.commit()

        return token_generator()    