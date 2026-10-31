"""SQLAlchemy async database setup (psycopg 3)."""

from app.core.config import get_settings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base


async_engine = create_async_engine(get_settings().database_url)
# expire_on_commit=False: attributes must stay readable after commit, a lazy reload would fail.
AsyncSessionLocal = async_sessionmaker(async_engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()
