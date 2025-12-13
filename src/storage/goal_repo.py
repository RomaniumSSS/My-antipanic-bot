"""
Goal Repository - CRUD operations for Goal and Stage models.

AICODE-NOTE: This is a dumb repository layer - only database access,
no business logic. Use-cases orchestrate these operations.
"""

import logging
from datetime import date
from typing import Optional

from src.database.models import Goal, Stage, User

logger = logging.getLogger(__name__)


async def get_active_goal(user: User) -> Optional[Goal]:
    """
    Get first active goal for user.

    Args:
        user: User instance

    Returns:
        Active Goal or None if no active goals exist
    """
    return await Goal.filter(user=user, status="active").order_by("id").first()


async def get_active_goals(user: User) -> list[Goal]:
    """
    Get all active goals for user.

    Args:
        user: User instance

    Returns:
        List of active Goals (empty list if none)
    """
    return await Goal.filter(user=user, status="active").order_by("id").all()


async def get_goal(goal_id: int) -> Optional[Goal]:
    """Get goal by ID."""
    return await Goal.get_or_none(id=goal_id)


async def get_active_stage(goal: Goal) -> Optional[Stage]:
    """
    Get current active stage for a goal.

    Returns first active stage ordered by order DESC, id DESC.
    This matches the logic from session.ensure_active_stage().

    Args:
        goal: Goal instance

    Returns:
        Active Stage or None if no active stages exist
    """
    return await Stage.filter(goal=goal, status="active").order_by("-order", "-id").first()


async def get_all_active_stages(goal: Goal) -> list[Stage]:
    """
    Get ALL active stages for a goal (for cleanup operations).

    Args:
        goal: Goal instance

    Returns:
        List of active Stages ordered by order DESC, id DESC
    """
    return await Stage.filter(goal=goal, status="active").order_by("-order", "-id").all()


async def get_pending_stages(goal: Goal) -> list[Stage]:
    """
    Get pending stages for a goal.

    Args:
        goal: Goal instance

    Returns:
        List of pending Stages ordered by order ASC
    """
    return await Stage.filter(goal=goal, status="pending").order_by("order").all()


async def get_all_stages(goal: Goal) -> list[Stage]:
    """Get all stages for a goal."""
    return await Stage.filter(goal=goal).order_by("order").all()


async def create_stage(
    goal: Goal,
    title: str,
    order: int,
    start_date: date,
    end_date: date,
    status: str = "pending",
) -> Stage:
    """
    Create a new stage.

    Args:
        goal: Parent Goal
        title: Stage title
        order: Stage order (1, 2, 3...)
        start_date: Stage start date
        end_date: Stage end date
        status: Stage status (default: "pending")

    Returns:
        Created Stage instance
    """
    return await Stage.create(
        goal=goal,
        title=title,
        order=order,
        start_date=start_date,
        end_date=end_date,
        status=status,
        progress=0,
    )


async def update_stage_status(stage: Stage, status: str) -> Stage:
    """
    Update stage status.

    Args:
        stage: Stage instance
        status: New status ("pending", "active", "completed")

    Returns:
        Updated Stage instance
    """
    stage.status = status
    await stage.save()
    return stage


async def save_goal(goal: Goal) -> Goal:
    """Save goal changes."""
    await goal.save()
    return goal


async def save_stage(stage: Stage) -> Stage:
    """Save stage changes."""
    await stage.save()
    return stage
