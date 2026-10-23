import asyncio
import redis.asyncio as redis

from app.core.config import get_settings


async def main() -> None:
    settings = get_settings()
    redis_url = settings.redis_url
    channel = settings.pubsub_channel

    client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)

    print(f"Subscribed to channel: {channel}")
    try:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                print(f"[PUBSUB] {message.get('channel')}: {message.get('data')}")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())