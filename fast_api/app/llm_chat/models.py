from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.db import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=True)
    system_prompt = Column(String(2000), nullable=True)
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    use_rag = Column(Boolean, nullable=False, default=False)
    rag_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    summary = Column(Text, nullable=True)                              # <-- new
    summarized_through_message_id = Column(Integer, nullable=True)     # <-- new
    use_tools = Column(Boolean, nullable=False, default=False)

    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    finish_reason = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(64), nullable=True)

    session = relationship("ChatSession", back_populates="messages")


class TextEmbedding(Base):
    __tablename__ = "text_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    chunk_index = Column(Integer, nullable=True)
    source_text = Column(Text, nullable=False)
    model = Column(String(100), nullable=False)
    embedding = Column(Vector(768), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
  