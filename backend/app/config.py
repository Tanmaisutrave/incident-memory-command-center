"""Configuration management using environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Hindsight
    hindsight_api_key: str = ""
    hindsight_base_url: str = "https://api.hindsight.vectorize.io"
    hindsight_bank_id: str = "incident-agent"
    
    # Groq
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    
    # Application
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    environment: str = "development"
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / '.env'),
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()
