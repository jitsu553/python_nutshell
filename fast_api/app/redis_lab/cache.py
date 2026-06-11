import json
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError


async def cache_get_json(redis: Redis, key: str) -> Any | None:
    try:
        raw = await redis.get(key)  # GET
    except RedisError:
        return None

    if raw is None:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def cache_set_json(redis: Redis, key: str, value: Any, ttl_seconds: int) -> None:
    payload = json.dumps(value, separators=(",", ":"), default=str)
    try:
        await redis.set(key, payload, ex=ttl_seconds)  # SET with EXPIRE in one call
    except RedisError:
        return


async def get_or_set_cache(
    redis: Redis,
    key: str,
    ttl_seconds: int,
    producer: Callable[[], Awaitable[Any]],
) -> tuple[Any, bool]:
    cached = await cache_get_json(redis, key)
    if cached is not None:
        return cached, True

    fresh = await producer()
    await cache_set_json(redis, key, fresh, ttl_seconds)
    return fresh, False