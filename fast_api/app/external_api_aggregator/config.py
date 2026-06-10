import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


def _env_bool_or_str(name: str, default: bool | str) -> bool | str:
    value = os.getenv(name)
    if value is None:
        return default

    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return value


@dataclass(frozen=True)
class ExternalAggregatorSettings:
    http_connect_timeout: float = _env_float("EXTERNAL_AGGREGATOR_HTTP_CONNECT_TIMEOUT", 3.0)
    http_read_timeout: float = _env_float("EXTERNAL_AGGREGATOR_HTTP_READ_TIMEOUT", 5.0)
    http_write_timeout: float = _env_float("EXTERNAL_AGGREGATOR_HTTP_WRITE_TIMEOUT", 3.0)
    http_pool_timeout: float = _env_float("EXTERNAL_AGGREGATOR_HTTP_POOL_TIMEOUT", 2.0)

    retry_max_attempts: int = _env_int("EXTERNAL_AGGREGATOR_RETRY_MAX_ATTEMPTS", 4)
    retry_min_wait_seconds: float = _env_float("EXTERNAL_AGGREGATOR_RETRY_MIN_WAIT_SECONDS", 1.0)
    retry_max_wait_seconds: float = _env_float("EXTERNAL_AGGREGATOR_RETRY_MAX_WAIT_SECONDS", 10.0)

    circuit_failure_threshold: int = _env_int("EXTERNAL_AGGREGATOR_CIRCUIT_FAILURE_THRESHOLD", 5)
    circuit_recovery_seconds: int = _env_int("EXTERNAL_AGGREGATOR_CIRCUIT_RECOVERY_SECONDS", 30)

    # For current environment default remains False. In production, set this env
    # var to True or a CA bundle path.
    ssl_verify: bool | str = _env_bool_or_str("EXTERNAL_AGGREGATOR_SSL_VERIFY", False)


settings = ExternalAggregatorSettings()
