"""
Конфигурация базы данных (Tortoise ORM).
Поддерживает SQLite (dev) и PostgreSQL (production).
"""

from src.config import config

TORTOISE_ORM = {
    "connections": {"default": config.database_url},
    "apps": {
        "models": {
            "models": ["src.database.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}
