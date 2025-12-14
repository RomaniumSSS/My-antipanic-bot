"""History API endpoints."""

from fastapi import APIRouter, Depends, Query

from src.database.models import Goal, Stage, Step, User
from src.interfaces.api import schemas
from src.interfaces.api.auth import get_current_user

router = APIRouter()


@router.get("/history", response_model=schemas.HistoryResponse)
async def get_history(
    user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100, description="Max items to return"),
):
    """Get user's history of completed steps.

    Args:
        user: Authenticated user
        limit: Maximum number of steps to return (default: 20, max: 100)

    Returns:
        HistoryResponse: List of completed steps
    """
    # Get all user's goals
    goals = await Goal.filter(user_id=user.telegram_id).all()
    goal_ids = [goal.id for goal in goals]

    # Get all stages for user's goals
    stages = await Stage.filter(goal_id__in=goal_ids).all()
    stage_ids = [stage.id for stage in stages]

    # Get completed steps, ordered by completion date
    completed_steps = (
        await Step.filter(
            stage_id__in=stage_ids,
            status="completed",
            completed_at__isnull=False,
        )
        .order_by("-completed_at")
        .limit(limit)
        .all()
    )

    # Format response
    steps = [
        schemas.StepHistoryItem(
            id=step.id,
            title=step.title,
            completed_at=step.completed_at,
            xp_reward=step.xp_reward,
            difficulty=step.difficulty,
        )
        for step in completed_steps
    ]

    return schemas.HistoryResponse(steps=steps)
