from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from src.bot.callbacks.data import RatingCallback
from src.bot.handlers.evening import cmd_evening, process_rating, update_streak
from src.database.models import DailyLog, User


class StubMessage:
    def __init__(self, user_id: int):
        self.from_user = SimpleNamespace(id=user_id)
        self.sent: list[str] = []
        self.edited: list[str] = []

    async def answer(self, text: str, reply_markup=None) -> None:  # noqa: ANN001
        self.sent.append(text)

    async def edit_text(self, text: str, reply_markup=None) -> None:  # noqa: ANN001
        self.edited.append(text)


class StubCallback:
    def __init__(self, user_id: int, message: StubMessage):
        self.from_user = SimpleNamespace(id=user_id)
        self.message = message
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


class StubState:
    def __init__(self):
        self.data: dict = {}
        self.state: str | None = None

    async def set_state(self, value) -> None:  # noqa: ANN001
        self.state = value

    async def get_state(self):  # noqa: ANN001
        return self.state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        return self.data

    async def clear(self) -> None:
        self.data = {}
        self.state = None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "days, expected_streak",
    [
        (["2025-12-01"], 1),
        (["2025-12-01", "2025-12-01"], 1),  # тот же день не увеличивает
        (["2025-12-01", "2025-12-02"], 2),
        (["2025-12-01", "2025-12-03"], 1),  # пропуск сбрасывает
    ],
)
async def test_update_streak_table(
    db: None, days: list[str], expected_streak: int
) -> None:
    """Проверяем базовые сценарии streak таблично."""
    user = await User.create(telegram_id=30)

    for day in days:
        update_streak(user, date.fromisoformat(day))

    assert user.streak_days == expected_streak
    assert user.streak_last_date == date.fromisoformat(days[-1])


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


@pytest.mark.asyncio
async def test_cmd_evening_without_morning_prompts_start(db: None) -> None:
    """Evening flow should guide user to morning when today is empty."""
    user = await User.create(telegram_id=901)
    message = StubMessage(user.telegram_id)
    state = StubState()

    await cmd_evening(message, state)

    assert any("ещё не было старта дня" in text for text in message.sent)
    assert state.state is None


@pytest.mark.asyncio
async def test_process_rating_twice_same_day_keeps_streak(db: None) -> None:
    """Calling evening rating twice in one day must not inflate streak."""
    today = date.today()
    user = await User.create(
        telegram_id=902, streak_days=1, streak_last_date=today - timedelta(days=1)
    )
    await DailyLog.create(user=user, date=today)

    message = StubMessage(user.telegram_id)
    callback = StubCallback(user.telegram_id, message)
    state = StubState()
    rating_data = RatingCallback(value=5)

    await process_rating(callback, rating_data, state)
    await user.refresh_from_db()
    first_streak = user.streak_days

    await process_rating(callback, rating_data, state)
    await user.refresh_from_db()

    assert first_streak == 2
    assert user.streak_days == 2

