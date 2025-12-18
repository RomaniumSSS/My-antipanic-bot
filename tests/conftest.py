import os
import sys

import pytest_asyncio
from tortoise import Tortoise

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest_asyncio.fixture(scope="function")
async def db() -> None:
    """Lightweight in-memory DB per test."""
    await Tortoise.init(
        db_url="sqlite://:memory:", modules={"models": ["src.database.models"]}
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


@pytest_asyncio.fixture
async def user(db):
    """Create a test user."""
    from src.database.models import User
    
    user = await User.create(
        telegram_id=123456789,
        username="test_user",
        first_name="Test",
    )
    return user
