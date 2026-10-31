from dotenv import load_dotenv

load_dotenv()  # Load .env for local development

from fastapi import FastAPI
import logging
import httpx
from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app import models as _models  # noqa: F401  registers every table with Base
from app.infra.database import async_engine
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup: same order as the old hooks; failures only warn so /docs stays up ---
    try:
        app.state.external_aggregator_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0),
            verify=get_settings().external_aggregator_ssl_verify,
        )
        logger.info("Created shared HTTP client for external_api_aggregator")
    except Exception as exc:
        logger.error("Failed to create HTTP client: %s", exc)

    try:
        await connect_redis(app)
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning("Redis connection skipped during startup: %s", exc)

    try:
        await connect_llm_client(app)
        logger.info("LLM Client connected")
    except Exception as exc:
        logger.warning("LLM Client connection skipped during startup: %s", exc)

    try:
        await start_workers(app)
    except Exception as exc:
        logger.warning("Document index workers not started: %s", exc)

    try:
        await connect_checkpointer(app)
        logger.info("LangGraph checkpointer connected")
    except Exception as exc:
        logger.warning("Checkpointer connection skipped during startup: %s", exc)

    yield  # the app serves requests here

    # --- shutdown: reverse of startup ---
    try:
        await close_checkpointer(app)
        logger.info("LangGraph checkpointer closed")
    except Exception as exc:
        logger.warning("Checkpointer shutdown warning: %s", exc)

    try:
        await stop_workers(app)
        await async_engine.dispose()
    except Exception as exc:
        logger.warning("Document workers shutdown warning: %s", exc)

    try:
        await close_llm_client(app)
        logger.info("LLM Client closed")
    except Exception as exc:
        logger.warning("LLM Client shutdown warning: %s", exc)

    try:
        await close_redis(app)
        logger.info("Redis closed")
    except Exception as exc:
        logger.warning("Redis shutdown warning: %s", exc)

    client = getattr(app.state, "external_aggregator_http_client", None)
    if client:
        try:
            await client.aclose()
            logger.info("Closed shared HTTP client")
        except Exception as exc:
            logger.error("Error closing HTTP client: %s", exc)


app = FastAPI(title="Python Nutshell FastAPI Demo",
              swagger_ui_parameters={"docExpansion": "none"},
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins.split(","),
    allow_credentials=True,  # you use httponly cookies; credentials require explicit origins, never "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(external_aggregator_router)
app.include_router(document_router)
app.include_router(llm_chat_router)
app.include_router(ticket_router)
app.include_router(customer_router)