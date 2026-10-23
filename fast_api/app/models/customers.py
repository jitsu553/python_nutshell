from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey

from app.infra.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    plan = Column(String(20), nullable=False, default="free")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    amount_cents = Column(Integer, nullable=False)
    reason = Column(String(500), nullable=False)
    issued_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    total_cents = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="placed")  # placed | shipped | cancelled
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)