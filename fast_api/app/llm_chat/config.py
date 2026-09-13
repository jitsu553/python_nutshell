from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"  # Ollama ignores the value but a header is still required
    llm_model: str = "mistral:latest"
    llm_embedding_model: str = "nomic-embed-text"   # <-- new
    llm_request_timeout_seconds: float = 60.0
    llm_max_context_tokens: int = 2048          # Ch3 — total context window budget
    llm_reserved_reply_tokens: int = 512        # Ch3 — headroom left for the model's answer
    llm_history_compact_threshold: int = 1024   # Ch6 — tokens of new history before summarizing
    llm_history_keep_raw_turns: int = 5         # Ch6 — recent turns always kept un-summarized
    llm_web_search_engine: str = "duckduckgo"


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()