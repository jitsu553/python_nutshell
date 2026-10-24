import uuid
from datetime import datetime

from sqlalchemy import Uuid, Column, DateTime, Float, ForeignKey, Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.infra.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=True)
    system_prompt = Column(String(2000), nullable=True)
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    use_rag = Column(Boolean, nullable=False, default=False)
    rag_document_id = Column(Uuid, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    summary = Column(Text, nullable=True)                              # <-- new
    summarized_through_message_id = Column(Uuid, nullable=True)     # <-- new
    use_tools = Column(Boolean, nullable=False, default=False)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at, ChatMessage.id",
        lazy="selectin",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id = Column(
        Uuid,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    finish_reason = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    tool_calls = Column(JSON(none_as_null=True), nullable=True)
    tool_call_id = Column(String(64), nullable=True)

    session = relationship("ChatSession", back_populates="messages")


class TextEmbedding(Base):
    __tablename__ = "text_embeddings"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id = Column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    chunk_index = Column(Integer, nullable=True)
    source_text = Column(Text, nullable=False)
    model = Column(String(100), nullable=False)
    embedding = Column(Vector(768), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class UserMemory(Base):
    __tablename__ = "user_memories"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class PendingApproval(Base):
    __tablename__ = "pending_approvals"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id = Column(
        Uuid,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name = Column(String(100), nullable=False)
    tool_args = Column(JSON(none_as_null=True), nullable=False)
    thread_id = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending | approved | rejected
    input_message_count = Column(Integer, nullable=False)
    requested_by_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_by_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)

    session = relationship("ChatSession")

class SentEmail(Base):
    __tablename__ = "sent_emails"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id = Column(Uuid, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    to_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    sent_by_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    provider_message_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    target_type = Column(String(50), nullable=False)
    target_id = Column(Uuid, nullable=True)
    details = Column(JSON(none_as_null=True), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id = Column(Uuid, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    organizer_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    start_at = Column(DateTime, nullable=False, index=True)  # UTC
    end_at = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)         
  