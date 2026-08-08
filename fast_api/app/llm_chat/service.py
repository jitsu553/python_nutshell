
from fastapi import HTTPException
from sqlalchemy.orm import Session
import httpx
import json

from .config import get_llm_settings
from .models import ChatMessage, ChatSession
from .schemas import CreateSessionRequest, PromptRequest
from app.db import SessionLocal


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