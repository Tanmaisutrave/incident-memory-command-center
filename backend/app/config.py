"""Configuration management using environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Hindsight
    hindsight_api_key: str = ""
    hindsight_base_url: str = "https://api.hindsight.vectorize.io"
    hindsight_bank_id: str = "incident-agent"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_max_tokens: int = 4000
    groq_reasoning_effort: bool = False

    # Application
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    environment: str = "development"

    # Logging
    log_level: str = "INFO"

    # ---------------------------------------------------------------------------
    # API security
    # ---------------------------------------------------------------------------

    # Required when ENVIRONMENT != development AND host is not loopback.
    # Set to a long random string (e.g. `openssl rand -hex 32`).
    app_api_key: str = ""

    # ---------------------------------------------------------------------------
    # Rate limiting / concurrency / call budgets
    # ---------------------------------------------------------------------------

    # Maximum simultaneous LLM + Hindsight calls (semaphore capacity).
    max_concurrent_calls: int = 4

    # 0 = disabled. Set to a positive integer to cap expensive (analyze/compare/
    # reflect) calls per calendar day or month.
    max_daily_calls: int = 0
    max_monthly_calls: int = 0

    # ---------------------------------------------------------------------------
    # Memory / retain settings
    # ---------------------------------------------------------------------------

    # When true, recall for production incidents is filtered to
    # environment=production only (using native SDK tag filtering).
    # If the SDK does not support tag filtering, results are post-filtered and
    # a warning is logged.
    recall_same_env_only: bool = True

    # When true, incidents from staging or development environments are NOT
    # retained to the shared memory bank.  Set to false only in development
    # workspaces where cross-environment learning is intentional.
    retain_non_production: bool = False

    # When true, a regex-based redaction pass (see redaction.py) is applied to
    # all content before it is retained to Hindsight and before it is sent to
    # the LLM.  Redacts emails, bearer tokens, AWS keys and PEM private-key blocks.
    memory_redaction: bool = True

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
