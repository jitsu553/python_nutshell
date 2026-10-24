from dotenv import load_dotenv

load_dotenv()  # Load .env for local development

from fastapi import FastAPI
import logging
import httpx
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app import models as _models  # noqa: F401  registers every table with Base
from app.infra.database import async_engine, init_db
from app.routers.system import router as system_router
from app.routers.auth import router as auth_router
from app.routers.aggregator import router as external_aggregator_router
from app.infra.redis_client import connect_redis, close_redis
from app.services.documents.indexer import start_workers, stop_workers
from app.routers.documents import router as document_router
from app.services.llm.client import connect_llm_client, close_llm_client 
from app.routers.llm_chat import router as llm_chat_router
from app.services.llm.graph import connect_checkpointer, close_checkpointer
from app.routers.tickets import router as ticket_router
from app.routers.customers import router as customer_router

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


app = FastAPI(title="Python Nutshell FastAPI Demo", swagger_ui_parameters={"docExpansion": "none"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins.split(","),
    allow_credentials=True,  # you use httponly cookies; credentials require explicit origins, never "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Starting FastAPI application...")

@app.on_event("startup")
async def on_startup():
    # Keep API docs available even when DB is temporarily unavailable.
    try:
        # auth_models.User.metadata.create_all(bind=engine)
        await init_db()
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
            verify=get_settings().external_aggregator_ssl_verify,
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

@app.on_event("startup")
async def startup_llm_client():
    try:
        await connect_llm_client(app)
        logger.info("LLM Client connected")
    except Exception as exc:
        logger.warning("LLM Client connection skipped during startup: %s", exc)

@app.on_event("startup")
async def startup_document_workers():
    try:
        await start_workers(app)
    except Exception as exc:
        logger.warning("Document index workers not started: %s", exc)

@app.on_event("startup")
async def startup_checkpointer():
    try:
        await connect_checkpointer(app)
        logger.info("LangGraph checkpointer connected")
    except Exception as exc:
        logger.warning("Checkpointer connection skipped during startup: %s", exc)

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
async def shutdown_document_workers():
    await stop_workers(app)
    await async_engine.dispose()

@app.on_event("shutdown")
async def shutdown_redis():
    try:
        await close_redis(app)
        logger.info("Redis closed")
    except Exception as exc:
        logger.warning("Redis shutdown warning: %s", exc)  

@app.on_event("shutdown")
async def shutdown_llm():
    try:
        await close_llm_client(app)
        logger.info("LLM Client closed")
    except Exception as exc:
        logger.warning("LLM Client shutdown warning: %s", exc)

@app.on_event("shutdown")
async def shutdown_checkpointer():
    try:
        await close_checkpointer(app)
        logger.info("LangGraph checkpointer closed")
    except Exception as exc:
        logger.warning("Checkpointer shutdown warning: %s", exc)

# Include routers
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(external_aggregator_router)
app.include_router(document_router)
app.include_router(llm_chat_router)
app.include_router(ticket_router)
app.include_router(customer_router)