from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.infra.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), unique=True, nullable=False)

    content_type = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", foreign_keys=[user_id])
    text_entry = relationship(
        "DocumentText",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    @property
    def index_status(self) -> str | None:
        # pending -> processing -> done | failed (retried) | dead (gave up)
        return self.text_entry.status if self.text_entry else None


class DocumentText(Base):
    __tablename__ = "document_texts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    extracted_text = Column(Text, nullable=False, default="")
    extracted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="text_entry")
    status = Column(String(20), nullable=False, default="pending", index=True)
    last_error = Column(String(1000), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    # Lease/retry deadline: a sweeper re-queues active rows once this passes
    next_retry_at = Column(DateTime, nullable=True, index=True)
