"""SQLAlchemy database setup."""

from app.core.config import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker


engine = create_engine(get_settings().database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS text_embeddings_embedding_hnsw_idx "
            "ON text_embeddings USING hnsw (embedding vector_cosine_ops)"
        ))
