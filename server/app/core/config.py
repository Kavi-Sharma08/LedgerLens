from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Anchor .env to the server package directory so the configured MongoDB URI is
# loaded regardless of the process working directory. A relative ".env" here
# silently falls back to defaults when scripts run from another folder, which
# has already caused data to land in an unintended local database.
SERVER_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVER_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application
    app_name: str = "LedgerLens API"
    environment: str = "development"
    debug: bool = True

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "ledgerlens"

    # Networking
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Authentication boundary: shared with Next.js (INTERNAL_API_SECRET).
    # FastAPI trusts identity headers only when this secret matches, so the
    # browser can never call protected endpoints directly. Auth.js owns all
    # actual authentication (OAuth, credentials, sessions).
    internal_api_secret: str = ""

    # AI provider (Phase 3). The key stays server-side and is never returned
    # to clients. The model name is configurable through the environment.
    ai_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    ai_request_timeout_seconds: int = 60
    ai_max_tool_rounds: int = 10
    # Upper bound on tokens the model may emit per completion.
    #
    # This value COUNTS AGAINST the provider's per-minute token budget together
    # with the input tokens. Groq's on-demand tier is capped at ~8000 TPM and
    # rejects any single request whose input + max_tokens exceeds it with HTTP
    # 413 "Payload Too Large". With 8192 reserved for output, EVERY request was
    # rejected before the model could answer (input ~1000 + 8192 > 8000) and the
    # UI showed "The AI assistant could not complete your request."
    #
    # 4096 leaves ample headroom for system prompt + tool schemas + evidence
    # (measured: ~1000-3000 tokens) while still producing long structured
    # JSON answers without hitting finish_reason="length".
    ai_max_tokens: int = 4096

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        """Allow comma-separated lists in env vars: "http://a,http://b"."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    if not settings.internal_api_secret:
        if settings.is_production:
            raise RuntimeError(
                "INTERNAL_API_SECRET must be set in production. It must match the "
                "Next.js client's INTERNAL_API_SECRET. Generate one with: "
                "python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Development without the secret still boots; authenticated endpoints
        # simply reject every call until the secret is configured.
        settings.internal_api_secret = ""

    return settings
