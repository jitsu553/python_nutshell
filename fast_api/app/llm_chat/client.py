from fastapi import FastAPI, Request
import httpx

from .config import get_llm_settings

LLM_APP_STATE_KEY = "llm_http_client"


async def connect_llm_client(app: FastAPI) -> None:
    settings = get_llm_settings()
    print(settings)
    client = httpx.AsyncClient(
        base_url=settings.llm_base_url,
        timeout=httpx.Timeout(settings.llm_request_timeout_seconds),
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
    )
    setattr(app.state, LLM_APP_STATE_KEY, client)


async def close_llm_client(app: FastAPI) -> None:
    client: httpx.AsyncClient | None = getattr(app.state, LLM_APP_STATE_KEY, None)
    if client is not None:
        await client.aclose()


def get_llm_client(request: Request) -> httpx.AsyncClient:
    client: httpx.AsyncClient | None = getattr(request.app.state, LLM_APP_STATE_KEY, None)
    if client is None:
        raise RuntimeError("LLM HTTP client is not initialized on app.state")
    return client