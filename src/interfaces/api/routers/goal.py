"""
Goals API router.

Endpoints:
- GET /api/goals - List user's goals
- GET /api/goals/{goal_id} - Get goal details with stages
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.database.models import Goal, User
from src.interfaces.api.auth import TelegramUser, get_current_user
from src.interfaces.api.schemas import (
    GoalDetailResponse,
    GoalListItem,
    GoalsListResponse,
    StageResponse,
)

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("", response_model=GoalsListResponse)
async def list_goals(
    tg_user: TelegramUser = Depends(get_current_user),
) -> GoalsListResponse:
    """
    List all goals for current user.

    Returns goals sorted by creation date (newest first).
    """
    user = await User.filter(telegram_id=tg_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    goals = await Goal.filter(user=user).order_by("-created_at")

    return GoalsListResponse(
        goals=[GoalListItem.model_validate(g) for g in goals],
        total=len(goals),
    )


@router.get("/{goal_id}", response_model=GoalDetailResponse)
async def get_goal(
    goal_id: int,
    tg_user: TelegramUser = Depends(get_current_user),
) -> GoalDetailResponse:
    """
    Get goal details with stages.

    Includes all stages with their progress and status.
    """
    user = await User.filter(telegram_id=tg_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    goal = await Goal.filter(id=goal_id, user=user).prefetch_related("stages").first()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found",
        )

    # Convert stages to response format
    stages = [
        StageResponse.model_validate(s)
        for s in sorted(goal.stages, key=lambda s: s.order)
    ]

    return GoalDetailResponse(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        start_date=goal.start_date,
        deadline=goal.deadline,
        status=goal.status,
        stages=stages,
    )
