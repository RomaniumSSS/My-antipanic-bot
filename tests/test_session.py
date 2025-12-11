from datetime import date, timedelta
import logging

import pytest

from src.database.models import DailyLog, Goal, Stage, Step, User
from src.services import session as session_service


def test_energy_from_tension_bounds() -> None:
    """Energy hint is clamped and defaults to 5 when unknown."""
    assert session_service._energy_from_tension(None) == 5
    assert session_service._energy_from_tension(0) == 8
    assert session_service._energy_from_tension(10) == 5
    assert session_service._energy_from_tension(30) == 2


def test_support_message_variants() -> None:
    """Support text adapts to delta direction."""
    assert "сдвиг" in session_service.support_message(before=7, after=4)
    assert "стабильно" in session_service.support_message(before=5, after=5)
    assert "сделал шаг" in session_service.support_message(before=3, after=5)
    assert "Круто" in session_service.support_message()


@pytest.mark.asyncio
async def test_get_body_micro_action_is_stable(db: None) -> None:
    """Body action should be deterministic per user to feel consistent."""
    user = await User.create(telegram_id=101)

    first = await session_service.get_body_micro_action(user)
    second = await session_service.get_body_micro_action(user)

    assert first == second
    assert first in session_service.BODY_ACTIONS


async def _goal_with_stage(
    user: User,
    *,
    goal: Goal | None = None,
    status: str = "active",
    progress: int = 0,
    order: int = 1,
) -> tuple[Goal, Stage]:
    if not goal:
        goal = await Goal.create(
            user=user,
            title=f"Goal {order}",
            deadline=date.today() + timedelta(days=7),
            start_date=date.today(),
            status="active",
        )
    stage = await Stage.create(
        goal=goal,
        title=f"Stage {order}",
        order=order,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=3),
        progress=progress,
        status=status,
    )
    return goal, stage


@pytest.mark.asyncio
async def test_ensure_active_stage_when_no_stage_creates_default(
    db: None, caplog: pytest.LogCaptureFixture
) -> None:
    """If goal lost all stages, ensure_active_stage should create a fallback."""
    user = await User.create(telegram_id=901)
    goal = await Goal.create(
        user=user,
        title="Recover",
        deadline=date.today() + timedelta(days=5),
        start_date=date.today(),
        status="active",
    )

    with caplog.at_level(logging.WARNING):
        current = await session_service.ensure_active_stage(goal)

    assert current is not None
    assert current.status == "active"
    assert current.order == 1
    assert current.goal_id == goal.id
    assert "has no stages" in caplog.text


@pytest.mark.asyncio
async def test_ensure_active_stage_when_missing_active_promotes_pending(
    db: None,
) -> None:
    """If sprint has no active stage, first pending should be activated."""
    user = await User.create(telegram_id=902)
    goal = await Goal.create(
        user=user,
        title="Pending only",
        deadline=date.today() + timedelta(days=10),
        start_date=date.today(),
        status="active",
    )
    stage = await Stage.create(
        goal=goal,
        title="Stage pending",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status="pending",
        progress=0,
    )

    current = await session_service.ensure_active_stage(goal)

    assert current is not None
    assert current.id == stage.id
    await stage.refresh_from_db()
    assert stage.status == "active"


@pytest.mark.asyncio
async def test_ensure_active_stage_when_multiple_stages_picks_latest_and_logs_warning(
    db: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Multiple active stages should be healed by keeping the latest one."""
    user = await User.create(telegram_id=903)
    goal = await Goal.create(
        user=user,
        title="Conflict goal",
        deadline=date.today() + timedelta(days=7),
        start_date=date.today(),
        status="active",
    )
    older = await Stage.create(
        goal=goal,
        title="Old active",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=3),
        status="active",
        progress=10,
    )
    newer = await Stage.create(
        goal=goal,
        title="New active",
        order=2,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=4),
        status="active",
        progress=5,
    )

    with caplog.at_level(logging.WARNING):
        current = await session_service.ensure_active_stage(goal)

    assert current is not None
    assert current.id == newer.id
    await older.refresh_from_db()
    assert older.status == "pending"
    assert "multiple active stages" in caplog.text


@pytest.mark.asyncio
async def test_ensure_active_stage_advances_and_completes(db: None) -> None:
    """Finished stage should complete and next pending becomes active, goal closes when done."""
    user = await User.create(telegram_id=201)
    goal, first = await _goal_with_stage(user, status="active", progress=100, order=1)
    _, second = await _goal_with_stage(user, goal=goal, status="pending", progress=0, order=2)

    current = await session_service.ensure_active_stage(goal)
    assert current is not None
    assert current.id == second.id

    await first.refresh_from_db()
    assert first.status == "completed"

    await second.refresh_from_db()
    second.progress = 100
    second.status = "active"  # ensure we don't overwrite active state with stale data
    await second.save()

    current_after = await session_service.ensure_active_stage(goal)
    await goal.refresh_from_db()
    await second.refresh_from_db()

    assert current_after is None
    assert second.status == "completed"
    assert goal.status == "completed"


@pytest.mark.asyncio
async def test_log_antipanic_action_tracks_assignment(db: None) -> None:
    """Logging a step attaches it to DailyLog and avoids double XP."""
    user = await User.create(telegram_id=301)
    goal, stage = await _goal_with_stage(user, status="active", progress=0)
    step = await Step.create(
        stage=stage,
        title="Micro",
        difficulty="easy",
        estimated_minutes=3,
        xp_reward=7,
        scheduled_date=date.today(),
        status="pending",
    )

    await session_service.log_antipanic_action(
        user=user, step=step, energy_hint=6, mood_hint="focused", completed=True
    )
    daily = await DailyLog.get(user=user, date=date.today())
    first_xp = daily.xp_earned

    assert step.id in daily.assigned_step_ids
    assert step.id in daily.completed_step_ids
    assert first_xp == step.xp_reward
    assert daily.energy_level == 6
    assert daily.mood_text == "focused"

    await session_service.log_antipanic_action(
        user=user, step=step, energy_hint=4, completed=True
    )
    updated = await DailyLog.get(user=user, date=date.today())
    assert updated.xp_earned == first_xp


@pytest.mark.asyncio
async def test_create_body_step_logs_daily(db: None) -> None:
    """Body step creation should attach to active stage and log energy."""
    user = await User.create(telegram_id=401)
    goal, _ = await _goal_with_stage(user, status="active", progress=0)

    step = await session_service.create_body_step(
        user=user, goal=goal, action_text="Размяться", tension=6
    )

    daily = await DailyLog.get(user=user, date=date.today())
    assert step.stage.goal_id == goal.id
    assert step.title == "Размяться"
    assert step.id in daily.assigned_step_ids
    assert daily.energy_level == session_service._energy_from_tension(6)


@pytest.mark.asyncio
async def test_get_task_micro_action_short_path(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Short micro action uses generate_micro_step and logs DailyLog entry."""
    user = await User.create(telegram_id=501)
    goal, _ = await _goal_with_stage(user, status="active", progress=0)

    async def fake_generate_micro_step(*args, **kwargs) -> str:
        return "Сделать короткий шаг"

    monkeypatch.setattr(session_service.ai_service, "generate_micro_step", fake_generate_micro_step)

    step = await session_service.get_task_micro_action(
        user=user, goal=goal, tension=4, max_minutes=5
    )

    daily = await DailyLog.get(user=user, date=date.today())
    assert step.title == "Сделать короткий шаг"
    assert 2 <= step.estimated_minutes <= 5
    assert step.xp_reward == 5
    assert step.id in daily.assigned_step_ids


@pytest.mark.asyncio
async def test_get_task_micro_action_long_path(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Longer sprint path should pick first fitting suggestion and map XP by difficulty."""
    user = await User.create(telegram_id=601)
    goal, _ = await _goal_with_stage(user, status="active", progress=0)

    async def fake_generate_steps(*args, **kwargs) -> list[dict]:
        return [
            {"title": "Быстрый прогресс", "minutes": 12, "difficulty": "medium"},
            {"title": "Запасной", "minutes": 25, "difficulty": "hard"},
        ]

    monkeypatch.setattr(session_service.ai_service, "generate_steps", fake_generate_steps)

    step = await session_service.get_task_micro_action(
        user=user, goal=goal, tension=2, max_minutes=20
    )

    daily = await DailyLog.get(user=user, date=date.today())
    assert step.title == "Быстрый прогресс"
    assert step.estimated_minutes == 12
    assert step.xp_reward == 20
    assert step.id in daily.assigned_step_ids

