import os
import sys
from datetime import date, timedelta

import pytest_asyncio
from tortoise import Tortoise

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def db() -> None:
    """Lightweight in-memory DB per test. Auto-applied to all tests."""
    await Tortoise.init(
        db_url="sqlite://:memory:", modules={"models": ["src.database.models"]}
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


@pytest_asyncio.fixture(scope="function")
async def test_user():
    """Create a test user for API tests."""
    from src.database.models import User, Goal, Stage

    # Create test user
    user = await User.create(
        telegram_id=123456789,
        username="testuser",
        first_name="Test",
        xp=50,
        level=2,
        streak_days=3,
        timezone_offset=0,
    )

    # Create test goal and stage
    goal = await Goal.create(
        user=user,
        title="Test Goal",
        status="active",
        start_date=date.today(),
        deadline=date.today() + timedelta(days=30),
    )

    await Stage.create(
        goal=goal,
        title="Test Stage",
        status="active",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=7),
        progress=50,
        order=1,
    )

    return user
