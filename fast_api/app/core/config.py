"""Single source of truth for configuration. Read env vars here, never with os.getenv elsewhere."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Fixed rules, not environment-driven.
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# Canonical media type we serve back during download.
PREFERRED_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}

# Accepted upload media types by extension.
# application/octet-stream is included because some clients send generic content type.
ALLOWED_CONTENT_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Core: no defaults, a missing value must stop the app, not weaken it ---
    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 60

    # --- HTTP / auth cookies ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"  # comma-separated
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM / MCP ---
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"  # Ollama ignores the value but a header is still required
    llm_model: str = "mistral:latest"
    llm_embedding_model: str = "nomic-embed-text"
    llm_request_timeout_seconds: float = 60.0
    llm_max_context_tokens: int = 2048  # total context window budget
    llm_reserved_reply_tokens: int = 512  # headroom left for the model's answer
    llm_history_compact_threshold: int = 1024  # tokens of new history before summarizing
    llm_history_keep_raw_turns: int = 5  # recent turns always kept un-summarized
    llm_web_search_engine: str = "duckduckgo"
    mcp_server_url: str = "http://localhost:8100/mcp"
    mcp_server_host: str = "0.0.0.0"
    mcp_server_port: int = 8100
    mcp_auth_token: str = ""

    # --- Documents ---
    documents_storage_dir: Path = Path("uploaded_documents")
    documents_max_file_size_bytes: int = 10 * 1024 * 1024
    documents_max_filename_length: int = 180
    documents_signature_read_bytes: int = 4096
    documents_storage_backend: str = "local"
    documents_s3_bucket_name: str = ""
    documents_s3_region: str = "ap-south-1"
    documents_s3_endpoint_url: str | None = None
    documents_s3_presigned_ttl_seconds: int = 300
    documents_index_max_attempts: int = 5
    documents_index_retry_base_seconds: int = 30
    documents_index_workers: int = 3  # parallel indexing jobs per pod
    documents_index_lease_seconds: int = 600  # a job not finished by then is re-queued
    documents_index_sweep_seconds: int = 30

    # --- External API aggregator ---
    external_aggregator_http_connect_timeout: float = 3.0
    external_aggregator_http_read_timeout: float = 5.0
    external_aggregator_http_write_timeout: float = 3.0
    external_aggregator_http_pool_timeout: float = 2.0
    external_aggregator_retry_max_attempts: int = 4
    external_aggregator_retry_min_wait_seconds: float = 1.0
    external_aggregator_retry_max_wait_seconds: float = 10.0
    external_aggregator_circuit_failure_threshold: int = 5
    external_aggregator_circuit_recovery_seconds: int = 30
    # Default stays False for the current environment. In production set True or a CA bundle path.
    external_aggregator_ssl_verify: bool | str = False

    @field_validator("documents_storage_backend")
    @classmethod
    def _lower_backend(cls, v: str) -> str:
        return v.lower()

    @field_validator("documents_s3_endpoint_url", mode="before")
    @classmethod
    def _blank_endpoint_is_none(cls, v):
        return (v.strip() or None) if isinstance(v, str) else v

    @field_validator("external_aggregator_ssl_verify", mode="before")
    @classmethod
    def _bool_or_ca_path(cls, v):
        # "true"/"false"/"1"/"0" -> bool, anything else is treated as a CA bundle path
        if isinstance(v, str):
            lowered = v.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached so .env is read once, not on every request."""
    return Settings()
