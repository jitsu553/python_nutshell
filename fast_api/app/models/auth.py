# app/auth/models.py
import uuid
from datetime import datetime

from sqlalchemy import Uuid, Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from app.infra.database import Base  # reuse the existing Base from db.py


class Role(Base):
    __tablename__ = "roles"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)   # "admin", "user"

    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    role_id = Column(Uuid, ForeignKey("roles.id"), nullable=True)
    role = relationship("Role", back_populates="users", lazy="selectin")

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    refresh_token = Column(String(512), unique=True, nullable=False)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")