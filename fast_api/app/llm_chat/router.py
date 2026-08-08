import json

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import httpx

from app.auth.dependencies import get_db
from .client import get_llm_client
from .config import get_llm_settings
from .schemas import PromptRequest, PromptResponse
from .service import build_payload
from .models import ChatSession
from .schemas import CreateSessionRequest, MessageResponse, SendMessageRequest, SessionResponse
from .service import ChatService

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