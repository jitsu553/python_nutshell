from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    default_cache_ttl_seconds: int = 60
    session_ttl_seconds: int = 1800


@lru_cache
def get_redis_settings() -> RedisSettings:
    return RedisSettings()