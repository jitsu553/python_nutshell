"""External API aggregator service with retries, timeouts, and health tracking."""

import asyncio
import logging
import re
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import settings
from .error_handling import CircuitBreaker, HealthTracker, classify_error
from .schemas import AggregateResponse, CryptoResponse, NewsItem, WeatherResponse

logger = logging.getLogger(__name__)

health_tracker = HealthTracker()

weather_circuit = CircuitBreaker(
    name="weather",
    failure_threshold=settings.circuit_failure_threshold,
    recovery_timeout_seconds=settings.circuit_recovery_seconds,
)
crypto_circuit = CircuitBreaker(
    name="crypto",
    failure_threshold=settings.circuit_failure_threshold,
    recovery_timeout_seconds=settings.circuit_recovery_seconds,
)
news_circuit = CircuitBreaker(
    name="news",
    failure_threshold=settings.circuit_failure_threshold,
    recovery_timeout_seconds=settings.circuit_recovery_seconds,
)


# ------------------------------------------------------------------
# Configuration (production-grade defaults)
# ------------------------------------------------------------------

TIMEOUT = httpx.Timeout(
    connect=settings.http_connect_timeout,
    read=settings.http_read_timeout,
    write=settings.http_write_timeout,
    pool=settings.http_pool_timeout,
)

RETRY_CONFIG = {
    "stop": stop_after_attempt(settings.retry_max_attempts),
    "wait": wait_exponential(
        multiplier=1,
        min=settings.retry_min_wait_seconds,
        max=settings.retry_max_wait_seconds,
    ),
    "retry": retry_if_exception_type(
        (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)
    ),
    "reraise": True,
}


# ------------------------------------------------------------------
# FETCHERS WITH RETRY LOGIC
# Each decorated with @retry for automatic resilience
# ------------------------------------------------------------------

@retry(**RETRY_CONFIG)
async def fetch_weather(client: httpx.AsyncClient) -> WeatherResponse:
    url = "https://wttr.in/London?format=3"
    response = await client.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    text = response.text.strip()
    parts = text.split(":", maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"Unexpected weather format: {text}")

    location = parts[0].strip()
    condition_with_temp = parts[1].strip()
    match = re.search(r"([+-]?\d+)\s*°C", condition_with_temp)
    if not match:
        raise ValueError(f"Cannot parse temperature from: {condition_with_temp}")

    temperature_c = int(match.group(1))
    condition = condition_with_temp[: match.start()].strip() or "unknown"

    return WeatherResponse(
        location=location,
        condition=condition,
        temperature_c=temperature_c,
    )


@retry(**RETRY_CONFIG)
async def fetch_crypto(client: httpx.AsyncClient) -> CryptoResponse:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd"}

    response = await client.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()

    data = response.json()
    price_usd = data.get("bitcoin", {}).get("usd")

    if price_usd is None:
        raise ValueError("CoinGecko response missing bitcoin/usd price")

    return CryptoResponse(
        symbol="bitcoin",
        price_usd=price_usd,
    )


@retry(**RETRY_CONFIG)
async def fetch_top_news(client: httpx.AsyncClient) -> NewsItem:
    ids_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    ids_response = await client.get(ids_url, timeout=TIMEOUT)
    ids_response.raise_for_status()

    story_ids = ids_response.json()
    if not story_ids:
        raise ValueError("HN returned empty story list")

    top_id = story_ids[0]

    item_url = f"https://hacker-news.firebaseio.com/v0/item/{top_id}.json"
    item_response = await client.get(item_url, timeout=TIMEOUT)
    item_response.raise_for_status()

    item_data = item_response.json()

    return NewsItem(
        id=item_data.get("id"),
        title=item_data.get("title", "No title"),
        author=item_data.get("by"),
        score=item_data.get("score", 0),
        url=item_data.get("url"),
    )


# ------------------------------------------------------------------
# AGGREGATOR SERVICE CLASS
# Orchestrates all three fetchers, handles partial failure
# ------------------------------------------------------------------

class AggregatorService:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client
        self._owns_client = client is None

    async def _ensure_client(self):
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=TIMEOUT, verify=settings.ssl_verify)

    async def fetch_all(self) -> AggregateResponse:
        await self._ensure_client()

        weather_pack, crypto_pack, news_pack = await asyncio.gather(
            self._safe_fetch_weather(),
            self._safe_fetch_crypto(),
            self._safe_fetch_news(),
        )

        weather, weather_failed = weather_pack
        crypto, crypto_failed = crypto_pack
        news, news_failed = news_pack

        failed_sources = [name for name in [weather_failed, crypto_failed, news_failed] if name]

        return AggregateResponse(
            weather=weather,
            crypto=crypto,
            news=news,
            failed_sources=failed_sources,
        )
    
    async def close(self):
        if self._owns_client and self.client:
            await self.client.aclose()

    async def __aenter__(self):
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def _safe_fetch_weather(self):
        if not weather_circuit.can_call():
            health_tracker.record_failure("weather", Exception("circuit_open"))
            return None, "weather"
        try:
            result = await fetch_weather(self.client)
            weather_circuit.record_success()
            health_tracker.record_success("weather")
            return result, None
        except Exception as exc:
            weather_circuit.record_failure(exc)
            health_tracker.record_failure("weather", exc)
            logger.warning("Weather failed (%s): %s", classify_error(exc).value, exc)
            return None, "weather"

    async def _safe_fetch_crypto(self):
        if not crypto_circuit.can_call():
            health_tracker.record_failure("crypto", Exception("circuit_open"))
            return None, "crypto"
        try:
            result = await fetch_crypto(self.client)
            crypto_circuit.record_success()
            health_tracker.record_success("crypto")
            return result, None
        except Exception as exc:
            crypto_circuit.record_failure(exc)
            health_tracker.record_failure("crypto", exc)
            logger.warning("Crypto failed (%s): %s", classify_error(exc).value, exc)
            return None, "crypto"

    async def _safe_fetch_news(self):
        if not news_circuit.can_call():
            health_tracker.record_failure("news", Exception("circuit_open"))
            return None, "news"
        try:
            result = await fetch_top_news(self.client)
            news_circuit.record_success()
            health_tracker.record_success("news")
            return result, None
        except Exception as exc:
            news_circuit.record_failure(exc)
            health_tracker.record_failure("news", exc)
            logger.warning("News failed (%s): %s", classify_error(exc).value, exc)
            return None, "news"

    def get_health_status(self) -> dict:
        return health_tracker.get_status()


# ------------------------------------------------------------------
# DEMO — Run the aggregator
# ------------------------------------------------------------------

async def demo():
    print("=== Aggregator Service Demo ===\n")

    async with AggregatorService() as aggregator:
        print("Fetching all three APIs concurrently...\n")
        response = await aggregator.fetch_all()

    print(f"Result:\n{response.model_dump_json(indent=2)}\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(demo())