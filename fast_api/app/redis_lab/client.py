from fastapi import FastAPI, Request
import redis.asyncio as redis
from redis.asyncio import Redis

from .config import get_redis_settings


REDIS_APP_STATE_KEY = "redis_client"


async def connect_redis(app: FastAPI) -> None:
    settings = get_redis_settings()
    client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        health_check_interval=30,
    )
    await client.ping()
    setattr(app.state, REDIS_APP_STATE_KEY, client)


async def close_redis(app: FastAPI) -> None:
    client: Redis | None = getattr(app.state, REDIS_APP_STATE_KEY, None)
    if client is not None:
        await client.aclose()


def get_redis_from_request(request: Request) -> Redis:
    client: Redis | None = getattr(request.app.state, REDIS_APP_STATE_KEY, None)
    if client is None:
        raise RuntimeError("Redis client is not initialized on app.state")
    return client