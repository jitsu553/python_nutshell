import json
from typing import Any
import logging

log = logging.getLogger(__name__)

from redis.asyncio import Redis
from redis.exceptions import RedisError


async def cache_get_json(redis: Redis, key: str) -> Any | None:
    try:
        raw = await redis.get(key)  # GET
    except RedisError as e:
        log.warning("redis cache unavailable, failing open: %s", e)
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
    except RedisError as e:
        log.warning("redis cache unavailable, failing open: %s", e)
        return None
