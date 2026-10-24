"""SQLAlchemy async database setup (psycopg 3)."""

from app.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base


async_engine = create_async_engine(get_settings().database_url)
# expire_on_commit=False: attributes must stay readable after commit, a lazy reload would fail.
AsyncSessionLocal = async_sessionmaker(async_engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS text_embeddings_embedding_hnsw_idx "
            "ON text_embeddings USING hnsw (embedding vector_cosine_ops)"
        ))
