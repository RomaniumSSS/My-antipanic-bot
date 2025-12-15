"""
Stats API router.

Endpoints:
- GET /api/stats - Get user statistics
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from src.database.models import DailyLog, Goal, Step, User
from src.interfaces.api.auth import TelegramUser, get_current_user
from src.interfaces.api.schemas import StatsResponse

router = APIRouter(prefix="/api", tags=["stats"])


# XP thresholds per level (level -> XP needed)
# AICODE-NOTE: Same formula as in src/core/domain/gamification.py
LEVEL_XP_THRESHOLDS = {
    1: 0,
    2: 100,
    3: 250,
    4: 450,
    5: 700,
    6: 1000,
    7: 1400,
    8: 1900,
    9: 2500,
    10: 3200,
}


def calculate_xp_to_next_level(level: int, current_xp: int) -> int:
    """Calculate XP needed to reach next level."""
    next_level = level + 1
    if next_level > 10:
        return 0  # Max level reached
    return max(0, LEVEL_XP_THRESHOLDS.get(next_level, 0) - current_xp)


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    tg_user: TelegramUser = Depends(get_current_user),
) -> StatsResponse:
    """
    Get user statistics.

    Includes:
    - Gamification (XP, level, streak)
    - Goal progress (total, active, completed)
    - Step completion stats
    """
    user = await User.filter(telegram_id=tg_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Goal stats
    goals = await Goal.filter(user=user)
    total_goals = len(goals)
    active_goals = sum(1 for g in goals if g.status == "active")
    completed_goals = sum(1 for g in goals if g.status == "completed")

    # Step completion stats
    # Get all steps via stages
    goal_ids = [g.id for g in goals]
    total_steps_completed = 0
    total_steps = 0

    if goal_ids:
        from src.database.models import Stage

        stages = await Stage.filter(goal_id__in=goal_ids)
        stage_ids = [s.id for s in stages]

        if stage_ids:
            steps = await Step.filter(stage_id__in=stage_ids)
            total_steps = len(steps)
            total_steps_completed = sum(1 for s in steps if s.status == "completed")

    # Today's steps
    today = date.today()
    daily_log = await DailyLog.filter(user=user, date=today).first()
    steps_today = 0
    if daily_log:
        steps_today = len(daily_log.completed_step_ids)

    # Completion rate
    completion_rate = 0.0
    if total_steps > 0:
        completion_rate = total_steps_completed / total_steps

    return StatsResponse(
        xp=user.xp,
        level=user.level,
        xp_to_next_level=calculate_xp_to_next_level(user.level, user.xp),
        streak_days=user.streak_days,
        total_goals=total_goals,
        active_goals=active_goals,
        completed_goals=completed_goals,
        total_steps_completed=total_steps_completed,
        steps_today=steps_today,
        completion_rate=round(completion_rate, 2),
    )
