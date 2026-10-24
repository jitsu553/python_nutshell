"""Standalone listener for document status events (run separately from the API):

    python -m app.services.documents.event_listener
"""
import asyncio

import redis.asyncio as redis

from app.core.config import get_settings
from app.services.documents.indexer import EVENTS_CHANNEL


async def main() -> None:
    client = redis.from_url(get_settings().redis_url, encoding="utf-8", decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)

    print(f"Subscribed to channel: {EVENTS_CHANNEL}")
    try:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                print(f"[DOCUMENT EVENT] {message.get('data')}")
    finally:
        await pubsub.unsubscribe(EVENTS_CHANNEL)
        await pubsub.aclose()
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
