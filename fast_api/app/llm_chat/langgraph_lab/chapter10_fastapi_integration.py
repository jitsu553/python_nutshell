"""
Chapter 10 — FastAPI integration: Chapter 9's graph, driven via SSE streaming.
Closely mirrors ChatService.send_message_stream() (service.py:411) — read them
side by side. Standalone demo app on its own port; your real router.py/service.py
are untouched.

Run from fast_api/:
    uvicorn app.llm_chat.langgraph_lab.chapter10_fastapi_integration:app --reload --port 8011

First create a session against your REAL app (same DB, so it's visible here too):
    curl -X POST http://localhost:8000/chat/sessions -H "Content-Type: application/json" \
         -d "{\"use_tools\": true}"
Then, against THIS app:
    curl -N -X POST http://localhost:8011/chat/stream -H "Content-Type: application/json" \
         -d "{\"session_id\": 1, \"message\": \"What is 340 * 12?\"}"
"""

from contextlib import asynccontextmanager

import openai
from fastapi import Depends, FastAPI, Request
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.llm_chat.config import get_llm_settings
from app.llm_chat.langgraph_lab.chapter9_chat_agent_graph import build_agent_graph
from app.llm_chat.models import ChatMessage
from app.llm_chat.service import ChatService, bind_overrides, format_sse, llm_error_detail
from app.llm_chat.tools import calculate, make_search_documents_tool, web_search


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_llm_settings()
    # Built once at startup — same idea as connect_llm_client() storing shared clients
    # on app.state instead of building one per request.
    app.state.llm = ChatOpenAI(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key,
        model=settings.llm_model, timeout=settings.llm_request_timeout_seconds,
    )
    app.state.embeddings = OpenAIEmbeddings(
        base_url=settings.llm_base_url, api_key=settings.llm_api_key,
        model=settings.llm_embedding_model, check_embedding_ctx_length=False,
    )
    yield


app = FastAPI(lifespan=lifespan)


def get_chat_service(request: Request, db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db, request.app.state.llm, request.app.state.embeddings)


class StreamMessageRequest(BaseModel):
    session_id: int
    message: str


async def stream_message_via_langgraph(chat_service: ChatService, session_id: int, content: str):
    session = chat_service.get_session_or_404(session_id)

    chat_service.db.add(ChatMessage(session_id=session.id, role="user", content=content))
    chat_service.db.commit()

    messages = await chat_service.build_session_messages(session, content)
    session_id_captured = session.id
    llm = bind_overrides(chat_service.llm, session.temperature, session.max_tokens)

    async def flush_assistant(msg):
        # Simplification vs. the real flush_assistant: this one doesn't also yield
        # a "tool_call" SSE frame announcing the call before it runs — just persists.
        chat_service.db.add(ChatMessage(
            session_id=session_id_captured, role="assistant", content=str(msg.content),
            tool_calls=msg.tool_calls or None,
            finish_reason=msg.response_metadata.get("finish_reason"),
        ))
        chat_service.db.commit()

    async def event_generator():
        try:
            tools = [calculate, make_search_documents_tool(chat_service.db, chat_service.embeddings), web_search]
            agent = build_agent_graph(llm, tools)

            collected_ai = None
            last_message_id = None

            async for chunk, _metadata in agent.astream(
                {"messages": messages}, config={"recursion_limit": 15}, stream_mode="messages",
            ):
                if chunk.type == "tool":
                    if collected_ai is not None:
                        await flush_assistant(collected_ai)
                        collected_ai = None
                        last_message_id = None
                    chat_service.db.add(ChatMessage(
                        session_id=session_id_captured, role="tool",
                        content=str(chunk.content), tool_call_id=chunk.tool_call_id,
                    ))
                    chat_service.db.commit()
                    continue

                if chunk.id != last_message_id:
                    if collected_ai is not None:
                        await flush_assistant(collected_ai)
                    collected_ai = chunk
                    last_message_id = chunk.id
                else:
                    collected_ai = collected_ai + chunk   # AIMessageChunk supports +, merges deltas

                if chunk.content:
                    yield format_sse({"delta": str(chunk.content)})

            if collected_ai is not None:
                await flush_assistant(collected_ai)
            yield format_sse({}, event="done")
        except openai.APIError as exc:
            yield format_sse({"detail": llm_error_detail(exc)}, event="stream_error")

    return event_generator()


@app.post("/chat/stream")
async def chat_stream(body: StreamMessageRequest, chat_service: ChatService = Depends(get_chat_service)):
    generator = await stream_message_via_langgraph(chat_service, body.session_id, body.message)
    return StreamingResponse(generator, media_type="text/event-stream")