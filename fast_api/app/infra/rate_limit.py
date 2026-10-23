import time
import logging

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from app.core.dependencies import get_current_user
from app.models.auth import User

from app.infra.redis_client import get_redis_from_request, get_optional_redis

log = logging.getLogger(__name__)


def _client_identifier(request: Request) -> str:
    """
    Prefer X-Forwarded-For (for reverse proxies), fallback to direct client IP.
    """
    xff = request.headers.get("x-forwarded-for")
    print("xff", xff)
    if xff:
        return xff.split(",")[0].strip()

    if request.client and request.client.host:
        print("client host", request.client.host)
        return request.client.host

    return "unknown"


def rate_limit(limit: int, window_seconds: int, key_prefix: str = "rl"):
    """
    Fixed-window rate limiter:
    - INCR counts requests in current time bucket
    - EXPIRE sets bucket TTL
    """

    async def dependency(
        request: Request,
        redis: Redis = Depends(get_redis_from_request),
    ) -> None:
        client_id = _client_identifier(request)
        bucket = int(time.time() // window_seconds)
        redis_key = f"{key_prefix}:{client_id}:{bucket}"

        try:
            current = await redis.incr(redis_key)
            if current == 1:
                await redis.expire(redis_key, window_seconds)
            ttl = await redis.ttl(redis_key)
        except RedisError:
            # Fail-open in production to protect availability when Redis is transiently down.
            return

        if current > limit:
            retry_after = max(ttl, 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please retry later.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency

def user_rate_limit(limit: int, window_seconds: int, key_prefix: str):
    """Fixed window per logged-in user. Fails open if Redis is down."""

    async def dependency(
        current_user: User = Depends(get_current_user),
        redis: Redis | None = Depends(get_optional_redis),
    ) -> None:
        if redis is None:
            return
        now = int(time.time())
        key = f"{key_prefix}:user-{current_user.id}:{now // window_seconds}"
        try:
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, window_seconds)
        except RedisError as e:
            log.warning("rate limit skipped, redis unavailable: %s", e)
            return
        if current > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many messages. Please slow down.",
                headers={"Retry-After": str(window_seconds - now % window_seconds)},
            )

    return dependency