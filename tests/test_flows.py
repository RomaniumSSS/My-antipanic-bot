from datetime import date, timedelta

import pytest

from src.bot.handlers.evening import update_streak
from src.bot.handlers.quiz import calculate_quiz_score
from src.database.models import DailyLog, Goal, Stage, User
from src.services import session as session_service


def test_calculate_quiz_score() -> None:
    """Score is scaled to 0-100 and diff is clamped at 0."""
    answers = [{"weight": 32}]
    score, diff = calculate_quiz_score(answers)
    assert score == 100
    assert diff == 65

    answers = [{"weight": 0}]
    score, diff = calculate_quiz_score(answers)
    assert score == 0
    assert diff == 0


@pytest.mark.asyncio
async def test_update_streak(db: None) -> None:
    """Streak increments day-to-day and resets after a gap."""
    user = await User.create(telegram_id=10, streak_days=2, streak_last_date=date.today() - timedelta(days=1))

    update_streak(user, date.today())
    assert user.streak_days == 3
    assert user.streak_last_date == date.today()

    update_streak(user, date.today() + timedelta(days=2))
    assert user.streak_days == 1
    assert user.streak_last_date == date.today() + timedelta(days=2)


@pytest.mark.asyncio
async def test_session_creates_body_and_micro_steps(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Antipanic session creates steps, logs them and keeps DailyLog consistent."""
    user = await User.create(telegram_id=99)
    goal = await Goal.create(
        user=user,
        title="Test goal",
        deadline=date.today() + timedelta(days=5),
        start_date=date.today(),
        status="active",
    )
    await Stage.create(
        goal=goal,
        title="Stage",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status="active",
    )

    async def fake_micro_step(*args, **kwargs) -> str:  # type: ignore[override]
        return "Сделать дыхательную разминку"

    monkeypatch.setattr(session_service.ai_service, "generate_micro_step", fake_micro_step)

    body_step = await session_service.create_body_step(
        user=user, goal=goal, action_text="Встряхнуться", tension=4
    )
    micro_step = await session_service.get_task_micro_action(
        user=user, goal=goal, tension=4, max_minutes=5
    )

    daily_log = await DailyLog.get(user=user, date=date.today())
    assert body_step.id in daily_log.assigned_step_ids
    assert micro_step.id in daily_log.assigned_step_ids
    assert daily_log.energy_level == session_service._energy_from_tension(4)

    # Mark micro step completed and ensure log updates XP
    micro_step.status = "completed"
    micro_step.completed_at = date.today()
    await micro_step.save()
    daily_log.completed_step_ids.append(micro_step.id)
    daily_log.xp_earned = (daily_log.xp_earned or 0) + micro_step.xp_reward
    await daily_log.save()

    updated_log = await DailyLog.get(user=user, date=date.today())
    assert micro_step.id in updated_log.completed_step_ids
    assert updated_log.xp_earned >= micro_step.xp_reward
