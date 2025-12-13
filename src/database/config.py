"""
Конфигурация базы данных (Tortoise ORM).
Поддерживает SQLite (dev) и PostgreSQL (production).
"""

import logging
import os

from src.config import config

logger = logging.getLogger(__name__)


def get_tortoise_db_url() -> str:
    """
    Get database URL with proper scheme for Tortoise ORM.

    Tortoise ORM requires 'postgres://' scheme, but Railway/Render
    provide 'postgresql://' URLs. This function ensures conversion.
    """
    # Try config.database_url first (has built-in conversion)
    url = config.database_url

    # Fallback: if still None or SQLite in production, check env directly
    # This handles edge cases where pydantic might not load env vars correctly
    if config.ENVIRONMENT == "production":
        env_url = os.environ.get("DATABASE_URL")
        if env_url and (not url or url.startswith("sqlite://")):
            logger.warning(
                f"Using DATABASE_URL from os.environ directly. "
                f"config.database_url was: {url}"
            )
            url = env_url

    # Ensure postgres:// scheme (Tortoise requirement)
    # postgresql:// -> postgres://
    if url.startswith("postgresql://"):
        url = "postgres://" + url[13:]  # len("postgresql://") = 13
        logger.info("Converted postgresql:// to postgres:// for Tortoise ORM")

    logger.info(
        f"Database URL scheme: {url.split('://')[0] if '://' in url else 'unknown'}"
    )

    return url


# Get URL at module load time
_db_url = get_tortoise_db_url()

TORTOISE_ORM = {
    "connections": {"default": _db_url},
    "apps": {
        "models": {
            "models": ["src.database.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}
