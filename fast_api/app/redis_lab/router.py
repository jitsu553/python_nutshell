import asyncio
import time
import httpx
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.external_api_aggregator.aggregator import fetch_crypto, fetch_top_news, fetch_weather
from app.external_api_aggregator.config import settings as external_aggregator_settings


from .rate_limit import rate_limit
from .cache import get_or_set_cache
from .client import get_redis_from_request
from .config import get_redis_settings

QUEUE_KEY = "queue:jobs:v1"

router = APIRouter(prefix="/redis-lab", tags=["redis-lab"])


@router.get("/health")
async def redis_health(redis: Redis = Depends(get_redis_from_request)) -> dict:
    pong = await redis.ping()
    return {"redis_ok": bool(pong)}

@router.get(
    "/rate-limited-demo",
    dependencies=[Depends(rate_limit(limit=100, window_seconds=60, key_prefix="rl:demo"))],
)
async def rate_limited_demo() -> dict:
    return {"ok": True, "message": "Within rate limit (100 requests/minute)."}


async def _external_summary(client: httpx.AsyncClient) -> dict:
    results = await asyncio.gather(
        fetch_weather(client),
        fetch_crypto(client),
        fetch_top_news(client),
        return_exceptions=True,
    )

    names = ["weather", "crypto", "news"]
    payload: dict = {"fetched_at_epoch": int(time.time()), "failed_sources": []}

    for name, result in zip(names, results):
        if isinstance(result, Exception):
            payload[name] = None
            payload["failed_sources"].append(name)
        else:
            payload[name] = result

    return payload


@router.get("/cache/external-summary")
async def cache_external_summary(
    request: Request,
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    settings = get_redis_settings()
    cache_key = "cache:external-summary:v1"

    async def producer() -> dict:
        shared_client = getattr(request.app.state, "external_aggregator_http_client", None)
        if shared_client is not None:
            return await _external_summary(shared_client)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(5.0),
            verify=external_aggregator_settings.ssl_verify,
        ) as local_client:
            return await _external_summary(local_client)

    data, cache_hit = await get_or_set_cache(
        redis=redis,
        key=cache_key,
        ttl_seconds=settings.default_cache_ttl_seconds,
        producer=producer,
    )

    ttl_seconds = await redis.ttl(cache_key)  # TTL
    return {
        "cache_key": cache_key,
        "cache_hit": cache_hit,
        "ttl_seconds": ttl_seconds,
        "data": data,
    }

class SetValueRequest(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: str
    ttl_seconds: int | None = Field(default=None, ge=1, le=86400)


class ListPushRequest(BaseModel):
    list_key: str = Field(min_length=1, max_length=200)
    value: str

@router.post("/commands/set")
async def redis_set(
    body: SetValueRequest,
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    if body.ttl_seconds is not None:
        await redis.set(body.key, body.value, ex=body.ttl_seconds)  # SET + EXPIRE
    else:
        await redis.set(body.key, body.value)  # SET

    ttl = await redis.ttl(body.key)  # TTL
    return {"key": body.key, "value": body.value, "ttl_seconds": ttl}


@router.get("/commands/get")
async def redis_get(
    key: str = Query(..., min_length=1),
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    value = await redis.get(key)  # GET
    ttl = await redis.ttl(key)    # TTL
    return {"key": key, "value": value, "ttl_seconds": ttl}


@router.post("/commands/expire")
async def redis_expire(
    key: str = Query(..., min_length=1),
    ttl_seconds: int = Query(..., ge=1, le=86400),
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    changed = await redis.expire(key, ttl_seconds)  # EXPIRE
    ttl = await redis.ttl(key)  # TTL
    return {"key": key, "expire_set": bool(changed), "ttl_seconds": ttl}


@router.post("/commands/list/push")
async def redis_list_push(
    body: ListPushRequest,
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    length = await redis.rpush(body.list_key, body.value)  # LIST push
    return {"list_key": body.list_key, "length": length}


@router.post("/commands/list/pop")
async def redis_list_pop(
    list_key: str = Query(..., min_length=1),
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    value = await redis.lpop(list_key)  # LIST pop
    length = await redis.llen(list_key)
    return {"list_key": list_key, "value": value, "length": length}    


class QueueEnqueueRequest(BaseModel):
    type: str = Field(min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)


class SessionCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    roles: list[str] = Field(default_factory=list)
    ttl_seconds: int | None = Field(default=None, ge=60, le=86400)


# ─── QUEUE ────────────────────────────────────────────────────────────────────

@router.post("/queue/enqueue")
async def queue_enqueue(
    body: QueueEnqueueRequest,
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    job = {
        "job_id": str(uuid.uuid4()),
        "type": body.type,
        "payload": body.payload,
        "created_at_epoch": int(time.time()),
    }
    length = await redis.rpush(QUEUE_KEY, json.dumps(job))   # push to tail
    return {"queue_key": QUEUE_KEY, "queue_length": length, "job": job}


@router.post("/queue/dequeue")
async def queue_dequeue(
    timeout_seconds: int = Query(default=1, ge=0, le=30),
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    item = await redis.blpop(QUEUE_KEY, timeout=timeout_seconds)  # blocking pop from head
    if item is None:
        return {"queue_key": QUEUE_KEY, "job": None}
    _, raw_value = item
    return {"queue_key": QUEUE_KEY, "job": json.loads(raw_value)}


@router.get("/queue/length")
async def queue_length(
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    length = await redis.llen(QUEUE_KEY)
    return {"queue_key": QUEUE_KEY, "queue_length": length}    

# ─── SESSIONS ─────────────────────────────────────────────────────────────────

@router.post("/sessions")
async def create_session(
    body: SessionCreateRequest,
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    settings = get_redis_settings()
    ttl = body.ttl_seconds or settings.session_ttl_seconds
    session_id = str(uuid.uuid4())
    key = f"session:{session_id}"

    data = {
        "user_id": body.user_id,
        "roles": body.roles,
        "created_at_epoch": int(time.time()),
    }

    await redis.set(key, json.dumps(data), ex=ttl)    # SET + EXPIRE
    return {"session_id": session_id, "key": key, "ttl_seconds": ttl}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    key = f"session:{session_id}"
    raw = await redis.get(key)            # GET
    if raw is None:
        raise HTTPException(status_code=404, detail="Session not found")
    ttl = await redis.ttl(key)            # TTL
    return {"session_id": session_id, "ttl_seconds": ttl, "data": json.loads(raw)}


@router.post("/sessions/{session_id}/touch")
async def touch_session(
    session_id: str,
    ttl_seconds: int = Query(default=1800, ge=60, le=86400),
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    key = f"session:{session_id}"
    exists = await redis.exists(key)
    if not exists:
        raise HTTPException(status_code=404, detail="Session not found")
    await redis.expire(key, ttl_seconds)  # EXPIRE refreshes TTL
    ttl = await redis.ttl(key)
    return {"session_id": session_id, "ttl_seconds": ttl}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    key = f"session:{session_id}"
    deleted = await redis.delete(key)
    return {"session_id": session_id, "deleted": bool(deleted)}

class PublishRequest(BaseModel):
    channel: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)

@router.post("/pubsub/publish")
async def publish_message(
    body: PublishRequest,
    redis: Redis = Depends(get_redis_from_request),
) -> dict:
    receivers = await redis.publish(body.channel, body.message)
    return {
        "channel": body.channel,
        "message": body.message,
        "receivers": receivers,
    }    