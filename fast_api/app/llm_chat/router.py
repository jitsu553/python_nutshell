import json

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import openai
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.auth.dependencies import get_db,get_current_user
from .client import get_llm_client, get_embeddings_client
from .config import get_llm_settings
from .models import ChatSession, TextEmbedding
from .schemas import ( 
    PromptRequest, PromptResponse, CreateSessionRequest, MessageResponse, SendMessageRequest, 
    SessionResponse, EmbedRequest, EmbedResponse, SimilarityRequest, SimilarityResponse,
    IngestResponse, SearchRequest, SearchResponse, SearchResult,
    RagAskRequest, RagAskResponse, RagSource
    )
from .service import (
    ChatService, build_payload, embed_texts, find_similar, 
    store_embedding, index_document_chunks, answer_with_context,
    stream_chat_completion, format_sse, bind_overrides, build_prompt_messages,
    llm_error_detail
)
from .utils.similarity import cosine_similarity
from app.auth.models import User


router = APIRouter(prefix="/llm-chat", tags=["llm-chat"])


@router.post("/prompt", response_model=PromptResponse)
async def send_prompt(
    body: PromptRequest,
    llm: ChatOpenAI = Depends(get_llm_client),
) -> PromptResponse:
    settings = get_llm_settings()

    messages = build_prompt_messages(body)

    model = bind_overrides(llm, body.temperature, body.max_tokens)

    try:
        response = await model.ainvoke(messages)
    except openai.APIError as exc:
        raise HTTPException(status_code=502, detail=llm_error_detail(exc))

    return PromptResponse(
        model=settings.llm_model,
        prompt=body.prompt,
        reply=str(response.content),
        finish_reason=response.response_metadata.get("finish_reason"),
    )


@router.post("/prompt/stream")
async def send_prompt_stream(
    body: PromptRequest,
    llm: ChatOpenAI = Depends(get_llm_client),
) -> StreamingResponse:
    messages = build_prompt_messages(body)

    model = bind_overrides(llm, body.temperature, body.max_tokens)

    async def event_generator():
        try:
            async for chunk in model.astream(messages):
                if chunk.content:
                    yield format_sse({"delta": str(chunk.content)})
        except openai.APIError as exc:
            yield format_sse({"detail": llm_error_detail(exc)}, event="stream_error")
            return
        yield format_sse({}, event="done")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
@router.post("/sessions", response_model=SessionResponse)
def create_chat_session(body: CreateSessionRequest, db: Session = Depends(get_db)) -> ChatSession:
    return ChatService(db).create_session(body)


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_chat_message(
    session_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    llm: ChatOpenAI = Depends(get_llm_client),
    embeddings: OpenAIEmbeddings = Depends(get_embeddings_client),
):
    service = ChatService(db, llm, embeddings)
    if body.stream is True:
        generator = await service.send_message_stream(session_id, body.content)
        return StreamingResponse(generator, media_type="text/event-stream")
    return await service.send_message(session_id, body.content)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def get_chat_messages(session_id: int, db: Session = Depends(get_db)):
    return ChatService(db).list_messages(session_id)


@router.post("/embeddings", response_model=EmbedResponse)
async def create_embeddings(
    body: EmbedRequest,
    embeddings: OpenAIEmbeddings = Depends(get_embeddings_client),
) -> EmbedResponse:
    return await embed_texts(body, embeddings)

@router.post("/similarity", response_model=SimilarityResponse)
async def compare_similarity(
    body: SimilarityRequest,
    embeddings: OpenAIEmbeddings = Depends(get_embeddings_client),
) -> SimilarityResponse:
    result = await embed_texts(EmbedRequest(input=[body.text_a, body.text_b]), embeddings)
    similarity = cosine_similarity(result.embeddings[0], result.embeddings[1])
    return SimilarityResponse(text_a=body.text_a, text_b=body.text_b, similarity=similarity)

@router.post("/store", response_model=IngestResponse)
async def ingest_texts(
    body: EmbedRequest,
    db: Session = Depends(get_db),
    embeddings: OpenAIEmbeddings = Depends(get_embeddings_client),
) -> IngestResponse:
    embed_result = await embed_texts(body, embeddings)
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
    embeddings: OpenAIEmbeddings = Depends(get_embeddings_client),
) -> SearchResponse:
    embed_result = await embed_texts(EmbedRequest(input=body.query), embeddings)
    matches = find_similar(db, embed_result.embeddings[0], limit=body.limit)
    return SearchResponse(
        query=body.query,
        results=[
            SearchResult(id=row.id, text=row.source_text, similarity=similarity,
                         document_id=row.document_id, chunk_index=row.chunk_index)
            for row, similarity in matches
        ],
    )

@router.post("/documents/{document_id}/index")
async def index_document_for_search(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embeddings: OpenAIEmbeddings = Depends(get_embeddings_client),
):
    rows = await index_document_chunks(db, document_id, current_user, embeddings)
    return {"document_id": document_id, "chunks_indexed": len(rows)}

@router.post("/ask", response_model=RagAskResponse)
async def ask_with_rag(
    body: RagAskRequest,
    db: Session = Depends(get_db),
    llm: ChatOpenAI = Depends(get_llm_client),
    embeddings: OpenAIEmbeddings = Depends(get_embeddings_client),
) -> RagAskResponse:
    embed_result = await embed_texts(EmbedRequest(input=body.question), embeddings)
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
    answer = await answer_with_context(body.question, chunks, llm)

    return RagAskResponse(
        question=body.question,
        answer=answer,
        sources=[
            RagSource(document_id=row.document_id, chunk_index=row.chunk_index, similarity=similarity, text=row.source_text)
            for row, similarity in matches
        ],
    )
