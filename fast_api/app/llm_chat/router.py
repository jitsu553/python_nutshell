import json

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import httpx

from app.auth.dependencies import get_db,get_current_user
from .client import get_llm_client
from .config import get_llm_settings
from .models import ChatSession, TextEmbedding
from .schemas import ( 
    PromptRequest, PromptResponse, CreateSessionRequest, MessageResponse, SendMessageRequest, 
    SessionResponse, EmbedRequest, EmbedResponse, SimilarityRequest, SimilarityResponse,
    IngestResponse, SearchRequest, SearchResponse, SearchResult,
    RagAskRequest, RagAskResponse, RagSource
    )
from .service import ChatService, build_payload, embed_texts, find_similar, store_embedding, index_document_chunks, find_similar, answer_with_context
from .utils.similarity import cosine_similarity
from app.auth.models import User


router = APIRouter(prefix="/llm-chat", tags=["llm-chat"])


@router.post("/prompt", response_model=PromptResponse)
async def send_prompt(
    body: PromptRequest,
    client: httpx.AsyncClient = Depends(get_llm_client),
) -> PromptResponse:
    settings = get_llm_settings()
    payload = build_payload(body)

    try:
        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc.response.text}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach LLM server: {exc}")

    data = response.json()
    choice = data["choices"][0]
    reply = choice["message"]["content"]
    finish_reason = choice.get("finish_reason")

    return PromptResponse(
        model=settings.llm_model,
        prompt=body.prompt,
        reply=reply,
        finish_reason=finish_reason,
    )


@router.post("/prompt/stream")
async def send_prompt_stream(
    body: PromptRequest,
    client: httpx.AsyncClient = Depends(get_llm_client),
) -> StreamingResponse:
    payload = build_payload(body, stream=True)

    async def token_generator():
        async with client.stream("POST", "/chat/completions", json=payload) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = await exc.response.aread()
                raise HTTPException(status_code=502, detail=f"LLM request failed: {detail.decode()}")

            async for line in response.aiter_lines():
                print(line)
                # yield line + "\n"
                if not line.startswith("data: "):
                    continue
                data = line.removeprefix("data: ").strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"].get("content")
                if delta:
                    yield delta

    return StreamingResponse(token_generator(), media_type="text/plain")

@router.post("/sessions", response_model=SessionResponse)
def create_chat_session(
    body: CreateSessionRequest,
    db: Session = Depends(get_db),
) -> ChatSession:
    service = ChatService(db, client=None)
    return service.create_session(body)


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_chat_message(
    session_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_llm_client),
):
    service = ChatService(db, client)

    if body.stream is True:
        generator = await service.send_message_stream(session_id, body.content)
        return StreamingResponse(generator, media_type="text/plain")

    return await service.send_message(session_id, body.content)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def get_chat_messages(
    session_id: int,
    db: Session = Depends(get_db),
):
    service = ChatService(db, client=None)
    return service.list_messages(session_id)


@router.post("/embeddings", response_model=EmbedResponse)
async def create_embeddings(
    body: EmbedRequest,
    client: httpx.AsyncClient = Depends(get_llm_client),
) -> EmbedResponse:
    return await embed_texts(body, client)

@router.post("/similarity", response_model=SimilarityResponse)
async def compare_similarity(
    body: SimilarityRequest,
    client: httpx.AsyncClient = Depends(get_llm_client),
) -> SimilarityResponse:
    result = await embed_texts(EmbedRequest(input=[body.text_a, body.text_b]), client)
    similarity = cosine_similarity(result.embeddings[0], result.embeddings[1])

    return SimilarityResponse(
        text_a=body.text_a,
        text_b=body.text_b,
        similarity=similarity,
    )

@router.post("/store", response_model=IngestResponse)
async def ingest_texts(
    body: EmbedRequest,
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_llm_client),
) -> IngestResponse:
    embed_result = await embed_texts(body, client)
    # print(embed_result)
    texts = body.input if isinstance(body.input, list) else [body.input]

    stored_ids = [
        store_embedding(db, text, vector, embed_result.model).id
        for text, vector in zip(texts, embed_result.embeddings)
    ]
    return IngestResponse(stored_ids=stored_ids)


@router.post("/search", response_model=SearchResponse)
async def search_texts(
    body: SearchRequest,
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_llm_client),
) -> SearchResponse:
    embed_result = await embed_texts(EmbedRequest(input=body.query), client)
    matches = find_similar(db, embed_result.embeddings[0], limit=body.limit)

    return SearchResponse(
        query=body.query,
        results=[
            SearchResult(
                id=row.id,
                text=row.source_text,
                similarity=similarity,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
            )
            for row, similarity in matches
        ],
    )

@router.post("/documents/{document_id}/index")
async def index_document_for_search(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_llm_client),
):
    rows = await index_document_chunks(db, document_id, current_user, client)
    return {"document_id": document_id, "chunks_indexed": len(rows)}

@router.post("/ask", response_model=RagAskResponse)
async def ask_with_rag(
    body: RagAskRequest,
    db: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_llm_client),
) -> RagAskResponse:
    embed_result = await embed_texts(EmbedRequest(input=body.question), client)
    matches = find_similar(
        db,
        embed_result.embeddings[0],
        limit=body.limit,
        document_id=body.document_id,
        min_similarity=body.min_similarity,
    )

    if not matches:
        return RagAskResponse(
            question=body.question,
            answer="I don't have enough relevant information to answer that.",
            sources=[],
        )

    chunks = [row for row, _similarity in matches]
    answer = await answer_with_context(body.question, chunks, client)

    return RagAskResponse(
        question=body.question,
        answer=answer,
        sources=[
            RagSource(document_id=row.document_id, chunk_index=row.chunk_index, similarity=similarity, text=row.source_text)
            for row, similarity in matches
        ],
    )
