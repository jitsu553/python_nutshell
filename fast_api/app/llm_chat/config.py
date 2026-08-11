from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"  # Ollama ignores the value but a header is still required
    llm_model: str = "mistral:latest"
    llm_embedding_model: str = "nomic-embed-text"   # <-- new
    llm_request_timeout_seconds: float = 60.0


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()