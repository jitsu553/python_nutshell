from dotenv import load_dotenv

load_dotenv()  # Load .env for local development

from fastapi import FastAPI
import logging
import httpx

from app.db import init_db
from app.routers.items import router as items_router
from app.routers.system import router as system_router
from app.routers.ml import router as ml_router
from app.auth.router import router as auth_router
from app.external_api_aggregator.config import settings as external_aggregator_settings
from app.external_api_aggregator.router import router as external_aggregator_router
from app.redis_lab.client import connect_redis, close_redis
from app.redis_lab.router import router as redis_lab_router
from app.document_service import models as document_models
from app.document_service.router import router as document_router

from app.auth import models as auth_models
from app.db import engine

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


app = FastAPI(title="Python Nutshell FastAPI Demo")

print("Starting FastAPI application...")

@app.on_event("startup")
def on_startup():
    # Keep API docs available even when DB is temporarily unavailable.
    try:
        auth_models.User.metadata.create_all(bind=engine)
        init_db()
        pass
    except Exception as exc:
        logger.warning("Database init skipped during startup: %s", exc)

# Startup hook for external_api_aggregator shared HTTP client
@app.on_event("startup")
async def startup_external_aggregator():
    """Create shared AsyncClient for aggregator service."""
    try:
        app.state.external_aggregator_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0),
            verify=external_aggregator_settings.ssl_verify,
        )
        logger.info("Created shared HTTP client for external_api_aggregator")
    except Exception as exc:
        logger.error(f"Failed to create HTTP client: {exc}")

@app.on_event("startup")
async def startup_redis():
    try:
        await connect_redis(app)
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning("Redis connection skipped during startup: %s", exc)        

# Shutdown hook for external_api_aggregator shared HTTP client
@app.on_event("shutdown")
async def shutdown_external_aggregator():
    """Close shared AsyncClient gracefully."""
    client = getattr(app.state, "external_aggregator_http_client", None)
    if client:
        try:
            await client.aclose()
            logger.info("Closed shared HTTP client")
        except Exception as exc:
            logger.error(f"Error closing HTTP client: {exc}")

@app.on_event("shutdown")
async def shutdown_redis():
    try:
        await close_redis(app)
        logger.info("Redis closed")
    except Exception as exc:
        logger.warning("Redis shutdown warning: %s", exc)            

# Include routers
app.include_router(system_router)
app.include_router(items_router)
app.include_router(ml_router)
app.include_router(auth_router)
app.include_router(external_aggregator_router)
app.include_router(redis_lab_router)
app.include_router(document_router)