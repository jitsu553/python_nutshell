from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, Request

from .aggregator import (
    AggregatorService,
    TIMEOUT,
    fetch_weather,
    fetch_crypto,
    fetch_top_news,
    health_tracker,
)
from .config import settings
from .schemas import AggregateResponse


router = APIRouter(
    prefix="/external-aggregator",
    tags=["external-api-aggregator"],
)


async def get_aggregator_service(request: Request) -> AsyncIterator[AggregatorService]:
    """
    Dependency that prefers a shared app-level client (production),
    but falls back to a request-local client for standalone learning.
    """
    shared_client = getattr(request.app.state, "external_aggregator_http_client", None)

    if shared_client is not None:
        # Reuse shared pool (best for production)
        yield AggregatorService(client=shared_client)
        return

    # Local fallback keeps this router usable even without app-level startup hooks.
    async with httpx.AsyncClient(timeout=TIMEOUT, verify=settings.ssl_verify) as local_client:
        yield AggregatorService(client=local_client)


async def fetch_all_sequential(client: httpx.AsyncClient) -> AggregateResponse:
    """
    Educational path: same three calls, but strictly one after another.
    Useful to compare latency with concurrent gather().
    """
    failed_sources: list[str] = []

    weather = None
    try:
        weather = await fetch_weather(client)
    except Exception:
        failed_sources.append("weather")

    crypto = None
    try:
        crypto = await fetch_crypto(client)
    except Exception:
        failed_sources.append("crypto")

    news = None
    try:
        news = await fetch_top_news(client)
    except Exception:
        failed_sources.append("news")

    return AggregateResponse(
        weather=weather,
        crypto=crypto,
        news=news,
        failed_sources=failed_sources,
    )


@router.get("/aggregate", response_model=AggregateResponse)
async def aggregate(
    service: AggregatorService = Depends(get_aggregator_service),
) -> AggregateResponse:
    """
    Production path: concurrent fan-out to weather/news/crypto.
    """
    return await service.fetch_all()


@router.get("/aggregate/compare")
async def compare_concurrent_vs_sequential(
    service: AggregatorService = Depends(get_aggregator_service),
) -> dict:
    """
    Learning endpoint:
    Runs concurrent and sequential versions and reports timing.
    """
    if service.client is None:
        # Defensive, dependency always provides one.
        return {"error": "No HTTP client available"}

    start_concurrent = time.perf_counter()
    concurrent_result = await service.fetch_all()
    concurrent_ms = (time.perf_counter() - start_concurrent) * 1000

    start_sequential = time.perf_counter()
    sequential_result = await fetch_all_sequential(service.client)
    sequential_ms = (time.perf_counter() - start_sequential) * 1000

    speedup = sequential_ms / concurrent_ms if concurrent_ms > 0 else None

    return {
        "concurrent_time_ms": round(concurrent_ms, 2),
        "sequential_time_ms": round(sequential_ms, 2),
        "speedup_x": round(speedup, 2) if speedup is not None else None,
        "concurrent_failed_sources": concurrent_result.failed_sources,
        "sequential_failed_sources": sequential_result.failed_sources,
    }

@router.get("/health")
async def health() -> dict:
    return health_tracker.get_status()