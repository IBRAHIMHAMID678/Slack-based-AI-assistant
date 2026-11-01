"""Application configuration management using Pydantic Settings.

Reads environment variables and local .env files with sensible defaults
for development, testing, and production deployment modes.
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for the AI Proposal Assistant."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Slack Credentials
    SLACK_BOT_TOKEN: str = "xoxb-mock-token"
    SLACK_APP_TOKEN: str = "xapp-mock-token"
    SLACK_SIGNING_SECRET: str = "mock-signing-secret"

    # LLM Configuration
    GROQ_API_KEY: str = "mock-groq-key"
    OPENROUTER_API_KEY: str = "mock-openrouter-key"
    LLM_MODE: Literal["mock", "live"] = "mock"

    # Storage Paths
    DATABASE_URL: str = "sqlite:///./proposals.db"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    PROPOSALS_DIR: str = "./data/proposals"
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"

    # Server & Runtime
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @property
    def is_mock_mode(self) -> bool:
        """Return True if LLM or Slack should run in mock mode."""
        return self.LLM_MODE == "mock" or (
            not self.GROQ_API_KEY.startswith("gsk_")
            and not self.OPENROUTER_API_KEY.startswith("sk-or-")
        )

    @property
    def base_dir(self) -> Path:
        """Return root application directory."""
        return Path(__file__).resolve().parent.parent


settings = Settings()
