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
