import asyncio
import os

import redis.asyncio as redis


async def main() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    channel = os.getenv("PUBSUB_CHANNEL", "events:demo")

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