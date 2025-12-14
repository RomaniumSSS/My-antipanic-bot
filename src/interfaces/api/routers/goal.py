"""Goal API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from src.database.models import User
from src.interfaces.api import schemas
from src.interfaces.api.auth import get_current_user
from src.storage import goal_repo

router = APIRouter()


@router.get("/goals", response_model=schemas.GoalResponse)
async def get_active_goal(user: User = Depends(get_current_user)):
    """Get user's active goal.

    Returns:
        GoalResponse: Active goal with current stage and progress

    Raises:
        HTTPException: If no active goal found
    """
    # Get active goal
    goal = await goal_repo.get_active_goal(user.telegram_id)
    if not goal:
        raise HTTPException(
            status_code=404,
            detail="No active goal. Please create a goal in the bot via /start",
        )

    # Get active stage
    stage = await goal_repo.get_active_stage(goal.id)

    return schemas.GoalResponse(
        id=goal.id,
        title=goal.title,
        current_stage=stage.title if stage else None,
        progress=stage.progress if stage else 0,
        deadline=goal.deadline.isoformat() if goal.deadline else None,
    )
