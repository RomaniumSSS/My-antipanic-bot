from datetime import date, timedelta

import pytest

from src.bot.handlers.morning import _get_or_create_onboarding_sprint_goal
from src.database.models import DailyLog, Goal, Stage, User
from src.services import session as session_service


@pytest.mark.asyncio
async def test_onboarding_sprint_goal_created_with_stage(db: None) -> None:
    """Creates onboarding goal and active stage when missing."""
    user = await User.create(telegram_id=701)

    goal = await _get_or_create_onboarding_sprint_goal(user)
    stage = await Stage.get(goal=goal)

    assert goal.status == "onboarding"
    assert stage.status == "active"
    assert stage.title == "Мини-спринт"
    assert stage.end_date == goal.deadline


@pytest.mark.asyncio
async def test_onboarding_sprint_goal_reused(db: None) -> None:
    """Does not duplicate onboarding goal if it already exists."""
    user = await User.create(telegram_id=702)
    existing = await Goal.create(
        user=user,
        title="Мини-спринт после квиза",
        description="Временная цель",
        start_date=date.today(),
        deadline=date.today() + timedelta(days=3),
        status="onboarding",
    )
    await Stage.create(
        goal=existing,
        title="Мини-спринт",
        order=1,
        start_date=date.today(),
        end_date=existing.deadline,
        status="active",
    )

    goal = await _get_or_create_onboarding_sprint_goal(user)

    assert goal.id == existing.id
    assert await Goal.filter(user=user, status="onboarding").count() == 1
    assert await Stage.filter(goal=goal).count() == 1


@pytest.mark.asyncio
async def test_morning_creates_new_log_even_if_evening_missing(db: None) -> None:
    """New morning flow should not be blocked by unfinished previous day."""
    user = await User.create(telegram_id=703)
    goal = await Goal.create(
        user=user,
        title="Main goal",
        start_date=date.today(),
        deadline=date.today() + timedelta(days=14),
        status="active",
    )
    stage = await Stage.create(
        goal=goal,
        title="Stage A",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=7),
        status="active",
        progress=0,
    )
    await DailyLog.create(
        user=user,
        date=date.today() - timedelta(days=1),
        assigned_step_ids=[111],
        completed_step_ids=[],
    )

    step = await session_service.create_body_step(
        user=user, goal=goal, action_text="Проснуться", tension=4
    )

    today_log = await DailyLog.get(user=user, date=date.today())
    assert step.id in today_log.assigned_step_ids
    assert today_log.completed_step_ids == []
    await stage.refresh_from_db()
    assert stage.status == "active"

