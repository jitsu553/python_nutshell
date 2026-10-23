import os

os.environ.setdefault("SECRET_KEY", "test-only-secret")  # tests never use the real key
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/fastapi_db")  # engine is lazy, no DB needed