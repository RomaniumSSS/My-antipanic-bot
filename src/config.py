"""
Конфигурация бота Antipanic.
Загружает переменные из .env файла.
"""

from typing import List, Union, Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: SecretStr
    
    # OpenAI
    OPENAI_KEY: SecretStr
    OPENAI_MODEL: str = "gpt-4o"
    
    # Alpha Testing: Whitelist (empty = open access)
    ALLOWED_USER_IDS: List[int] = []

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("ALLOWED_USER_IDS", mode="before")
    @classmethod
    def parse_allowed_ids(cls, v: Union[str, List[Any]]) -> List[int]:
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


config = Settings()
