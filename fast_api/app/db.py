"""SQLAlchemy database setup and CRUD helpers."""

import os
from typing import Optional

from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/fastapi_db"

DATABASE_URL = os.getenv(
	"DATABASE_URL",
	"postgresql+psycopg://postgres:postgres@localhost:5432/fastapi_db",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ItemModel(Base):
	__tablename__ = "items"

	item_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
	name = Column(String, nullable=False)
	price = Column(Float, nullable=False)
	description = Column(String, nullable=True)

	def to_dict(self) -> dict:
		return {
			"item_id": self.item_id,
			"name": self.name,
			"price": self.price,
			"description": self.description,
		}


def init_db() -> None:
	Base.metadata.create_all(bind=engine)


def create_item(item: dict) -> dict:
	session = SessionLocal()
	try:
		db_item = ItemModel(
			name=item["name"],
			price=item["price"],
			description=item.get("description"),
		)
		session.add(db_item)
		session.commit()
		session.refresh(db_item)
		return db_item.to_dict()
	finally:
		session.close()


def update_item(item_id: int, item: dict) -> Optional[dict]:
	session = SessionLocal()
	try:
		db_item = session.query(ItemModel).filter(ItemModel.item_id == item_id).first()
		if db_item is None:
			return None

		db_item.name = item["name"]
		db_item.price = item["price"]
		db_item.description = item.get("description")
		session.commit()
		session.refresh(db_item)
		return db_item.to_dict()
	finally:
		session.close()


def delete_item(item_id: int) -> bool:
	session = SessionLocal()
	try:
		db_item = session.query(ItemModel).filter(ItemModel.item_id == item_id).first()
		if db_item is None:
			return False

		session.delete(db_item)
		session.commit()
		return True
	finally:
		session.close()


def get_item_by_id(item_id: int) -> Optional[dict]:
	session = SessionLocal()
	try:
		db_item = session.query(ItemModel).filter(ItemModel.item_id == item_id).first()
		if db_item is None:
			return None
		return db_item.to_dict()
	finally:
		session.close()


def get_all_items() -> list[dict]:
	session = SessionLocal()
	try:
		db_items = session.query(ItemModel).order_by(ItemModel.item_id.asc()).all()
		return [db_item.to_dict() for db_item in db_items]
	finally:
		session.close()
