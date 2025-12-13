"""
Конфигурация бота Antipanic.
Загружает переменные из .env файла.
"""

from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: SecretStr

    # OpenAI
    OPENAI_KEY: SecretStr
    # Используем более мощную модель по умолчанию
    OPENAI_MODEL: str = "gpt-4.1"

    # Alpha Testing: Whitelist (empty = open access)
    ALLOWED_USER_IDS: list[int] = []

    # Database URL (Railway/Render format)
    # If set, overrides PostgreSQL individual vars
    DATABASE_URL: str | None = None

    # PostgreSQL (individual vars, fallback if DATABASE_URL not set)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "antipanic"
    POSTGRES_USER: str = "antipanic"
    POSTGRES_PASSWORD: SecretStr | None = None

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Environment (development | production)
    ENVIRONMENT: str = "development"

    # Webhook (for production)
    WEBHOOK_URL: str | None = None
    WEBHOOK_PATH: str = "/webhook"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("ALLOWED_USER_IDS", mode="before")
    @classmethod
    def parse_allowed_ids(cls, v: str | list[Any]) -> list[int]:
        if isinstance(v, str):
            if not v.strip():
                return []
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json

                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        return v

    @property
    def database_url(self) -> str:
        """
        Get database URL based on environment.

        Priority:
        1. DATABASE_URL env var (Railway/Render format)
        2. PostgreSQL individual vars (production)
        3. SQLite (development)
        """
        # 1. Use DATABASE_URL if provided (Railway/Render)
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # Railway uses postgres://, but asyncpg needs postgresql://
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url

        # 2. Production: construct from individual vars
        if self.ENVIRONMENT == "production":
            if not self.POSTGRES_PASSWORD:
                raise ValueError("POSTGRES_PASSWORD required for production")
            return (
                f"postgresql://{self.POSTGRES_USER}:"
                f"{self.POSTGRES_PASSWORD.get_secret_value()}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

        # 3. Development: SQLite
        return "sqlite://db.sqlite3"

    @property
    def redis_url(self) -> str:
        """Get Redis URL."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


config = Settings()
