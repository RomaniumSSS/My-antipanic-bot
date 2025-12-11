from datetime import date, timedelta

import pytest

from src.bot.handlers.evening import update_streak
from src.database.models import User


@pytest.mark.asyncio
async def test_update_streak_same_day_keeps_count(db: None) -> None:
    """Calling twice in one day should not inflate streak."""
    today = date.today()
    user = await User.create(
        telegram_id=21, streak_days=4, streak_last_date=today
    )

    update_streak(user, today)

    assert user.streak_days == 4
    assert user.streak_last_date == today


@pytest.mark.asyncio
async def test_update_streak_gap_resets(db: None) -> None:
    """Gap larger than one day resets streak to 1."""
    today = date.today()
    user = await User.create(
        telegram_id=22, streak_days=5, streak_last_date=today - timedelta(days=3)
    )

    update_streak(user, today)

    assert user.streak_days == 1
    assert user.streak_last_date == today

