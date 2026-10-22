from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db
from app.redis_lab.client import get_optional_redis

router = APIRouter()


@router.get("/")
def root():
    return {"message": "FastAPI is running"}


@router.get("/health")
def health():
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(response: Response, db: Session = Depends(get_db), redis=Depends(get_optional_redis)):
    """Readiness: Postgres is required (503 without it). Redis is optional because we fail open."""
    checks = {}
    try:
        db.execute(text("select 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "down"
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:  # also covers redis being None
        checks["redis"] = "down"
    if checks["postgres"] != "ok":
        response.status_code = 503
    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, **checks}