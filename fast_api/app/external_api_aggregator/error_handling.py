"""
Chapter 09 — Error Handling & Graceful Degradation
Run: python error_handling.py

Concepts:
  - Error classification (transient vs permanent)
  - Fallback values (sensible defaults)
  - Health status tracking
  - Observability (logging, metrics)
  - Circuit breaker pattern (optional)
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

import httpx


logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# ERROR CLASSIFICATION
# Different error types need different handling strategies
# ------------------------------------------------------------------

class ErrorType(str, Enum):
    """Classify errors for intelligent retry/fallback decisions."""
    
    # Transient — retry will likely succeed
    NETWORK_TIMEOUT = "network_timeout"
    CONNECTION_ERROR = "connection_error"
    SERVER_OVERLOAD = "server_overload"  # 503, 429
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    
    # Permanent — retry won't help
    NOT_FOUND = "not_found"  # 404
    INVALID_REQUEST = "invalid_request"  # 400
    AUTHENTICATION_FAILED = "authentication_failed"  # 401, 403
    BAD_RESPONSE_FORMAT = "bad_response_format"
    
    # Unknown
    UNKNOWN = "unknown"


def classify_error(exc: Exception) -> ErrorType:
    """
    Classify an exception to decide retry/fallback strategy.
    
    Transient errors → try again
    Permanent errors → use fallback immediately
    """
    if isinstance(exc, httpx.TimeoutException):
        return ErrorType.NETWORK_TIMEOUT
    
    if isinstance(exc, httpx.ConnectError):
        return ErrorType.CONNECTION_ERROR
    
    if isinstance(exc, httpx.HTTPStatusError):
        response = getattr(exc, "response", None)
        status = response.status_code if response is not None else None
        if status is None:
            return ErrorType.UNKNOWN
        if status == 404:
            return ErrorType.NOT_FOUND
        elif 400 <= status < 404:
            return ErrorType.INVALID_REQUEST
        elif 401 <= status <= 403:
            return ErrorType.AUTHENTICATION_FAILED
        elif status == 429:
            return ErrorType.SERVER_OVERLOAD
        elif status == 503:
            return ErrorType.TEMPORARY_UNAVAILABLE
        elif status >= 500:
            return ErrorType.SERVER_OVERLOAD
    
    if isinstance(exc, ValueError):
        # Parsing error — bad response format
        return ErrorType.BAD_RESPONSE_FORMAT
    
    return ErrorType.UNKNOWN


# ------------------------------------------------------------------
# FALLBACK VALUES
# Sensible defaults when APIs fail
# ------------------------------------------------------------------

@dataclass
class FallbackData:
    """Fallback values returned when APIs are unavailable."""
    
    weather: str = "Unknown (API unavailable)"
    crypto_price: float = 0.0  # 0 = "no data", not "price is zero"
    crypto_symbol: str = "unknown"
    news_title: str = "No news available"
    news_score: int = 0
    
    def to_dict(self):
        return {
            "weather": self.weather,
            "crypto": {
                "symbol": self.crypto_symbol,
                "price_usd": self.crypto_price,
            },
            "news": {
                "title": self.news_title,
                "score": self.news_score,
            },
        }


# ------------------------------------------------------------------
# CIRCUIT BREAKER PATTERN (optional but production-grade)
#
# If API fails N times in a row, stop calling it for a while
# This protects a struggling upstream from being hammered
# ------------------------------------------------------------------

class CircuitBreaker:
    """
    Simple circuit breaker for API resilience.
    
    States:
      CLOSED   → normal operation (call the API)
      OPEN     → API is failing (don't call it, return fallback)
      HALF_OPEN → testing if API recovered
    """
    
    class State(str, Enum):
        CLOSED = "closed"      # Normal
        OPEN = "open"          # Stop calling
        HALF_OPEN = "half_open"  # Testing recovery
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 30,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: API name (for logging)
            failure_threshold: fail N times → open circuit
            recovery_timeout_seconds: after this, try again
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout_seconds)
        
        self.state = self.State.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
    
    def record_success(self):
        """Called when API call succeeds."""
        logger.info(f"CircuitBreaker({self.name}): success")
        self.failure_count = 0
        self.state = self.State.CLOSED
    
    def record_failure(self, exc: Exception):
        """Called when API call fails."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        logger.warning(
            f"CircuitBreaker({self.name}): failure #{self.failure_count} "
            f"({classify_error(exc).value})"
        )
        
        if self.failure_count >= self.failure_threshold:
            logger.error(
                f"CircuitBreaker({self.name}): OPENING circuit "
                f"({self.failure_count} failures)"
            )
            self.state = self.State.OPEN
    
    def can_call(self) -> bool:
        """Check if we should attempt the API call."""
        if self.state == self.State.CLOSED:
            return True
        
        if self.state == self.State.OPEN:
            # Check if recovery timeout elapsed
            if (
                self.last_failure_time
                and datetime.utcnow() - self.last_failure_time > self.recovery_timeout
            ):
                logger.info(
                    f"CircuitBreaker({self.name}): recovery timeout expired, "
                    "going HALF_OPEN"
                )
                self.state = self.State.HALF_OPEN
                return True
            return False
        
        # HALF_OPEN: try one call to test recovery
        return True


# ------------------------------------------------------------------
# HEALTH STATUS ENDPOINT
# Track API availability and error rates
# ------------------------------------------------------------------

@dataclass
class APIHealth:
    """Health status of a single upstream API."""
    
    name: str
    is_healthy: bool
    last_error: Optional[str] = None
    error_count: int = 0
    last_check_time: Optional[datetime] = None
    
    def to_dict(self):
        return {
            "name": self.name,
            "status": "healthy" if self.is_healthy else "unhealthy",
            "last_error": self.last_error,
            "error_count": self.error_count,
            "last_check_time": self.last_check_time.isoformat()
            if self.last_check_time
            else None,
        }


class HealthTracker:
    """Track health of all upstream APIs."""
    
    def __init__(self):
        self.weather_health = APIHealth(name="weather", is_healthy=True)
        self.crypto_health = APIHealth(name="crypto", is_healthy=True)
        self.news_health = APIHealth(name="news", is_healthy=True)
    
    def record_success(self, api_name: str):
        """Mark an API as healthy."""
        health = getattr(self, f"{api_name}_health")
        health.is_healthy = True
        health.error_count = 0
        health.last_check_time = datetime.utcnow()
    
    def record_failure(self, api_name: str, exc: Exception):
        """Mark an API as unhealthy."""
        health = getattr(self, f"{api_name}_health")
        health.is_healthy = False
        health.last_error = f"{type(exc).__name__}: {str(exc)[:100]}"
        health.error_count += 1
        health.last_check_time = datetime.utcnow()
        
        logger.warning(
            f"API {api_name} unhealthy: {health.last_error}"
        )
    
    def get_status(self) -> dict:
        """Return health status of all APIs."""
        all_healthy = all([
            self.weather_health.is_healthy,
            self.crypto_health.is_healthy,
            self.news_health.is_healthy,
        ])
        
        return {
            "overall": "healthy" if all_healthy else "degraded",
            "apis": [
                self.weather_health.to_dict(),
                self.crypto_health.to_dict(),
                self.news_health.to_dict(),
            ],
        }


# ------------------------------------------------------------------
# DEMO — Error handling strategies
# ------------------------------------------------------------------

def demo_error_classification():
    """Show how errors are classified."""
    print("=== DEMO 1: Error Classification ===\n")
    
    request = httpx.Request("GET", "https://example.com")
    errors = [
        httpx.TimeoutException("timed out"),
        httpx.ConnectError("connection refused"),
        httpx.HTTPStatusError(
            "404 Not Found",
            request=request,
            response=httpx.Response(404, request=request),
        ),
        httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=request,
            response=httpx.Response(503, request=request),
        ),
        ValueError("JSON parse error"),
    ]
    
    for exc in errors:
        error_type = classify_error(exc)
        print(f"{type(exc).__name__:25} → {error_type.value}")
    print()


def demo_circuit_breaker():
    """Show circuit breaker state transitions."""
    print("=== DEMO 2: Circuit Breaker ===\n")
    
    cb = CircuitBreaker(name="weather", failure_threshold=3, recovery_timeout_seconds=5)
    
    # Simulate 3 failures
    for i in range(3):
        cb.record_failure(Exception("API error"))
        print(f"After failure {i+1}: state={cb.state.value}, can_call={cb.can_call()}")
    
    # Circuit is now OPEN
    print(f"\nCircuit is OPEN. can_call() = {cb.can_call()}")
    print("(Would not call the API)")
    
    # Simulate time passing and recovery check
    print("\nAfter recovery timeout, go HALF_OPEN and test...")
    cb.state = CircuitBreaker.State.HALF_OPEN
    cb.last_failure_time = datetime.utcnow() - timedelta(seconds=10)
    cb.record_success()
    print(f"After success: state={cb.state.value}, can_call={cb.can_call()}\n")


def demo_health_tracking():
    """Show health tracking."""
    print("=== DEMO 3: Health Tracking ===\n")
    
    tracker = HealthTracker()
    
    # Weather succeeds
    tracker.record_success("weather")
    
    # Crypto fails
    tracker.record_failure("crypto", httpx.TimeoutException("timed out"))
    
    # News fails
    tracker.record_failure("news", ValueError("parse error"))
    
    import json
    status = tracker.get_status()
    print(f"Status:\n{json.dumps(status, indent=2, default=str)}\n")


def demo_fallback_values():
    """Show fallback behavior."""
    print("=== DEMO 4: Fallback Values ===\n")
    
    fallback = FallbackData()
    
    print("When all APIs fail, return:")
    import json
    print(json.dumps(fallback.to_dict(), indent=2))
    print("\nClient gets partial/empty data instead of error 5xx\n")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo_error_classification()
    demo_circuit_breaker()
    demo_health_tracking()
    demo_fallback_values()