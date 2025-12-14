"""Statistics API endpoints."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from src.database.models import DailyLog, Step, User
from src.interfaces.api import schemas
from src.interfaces.api.auth import get_current_user

router = APIRouter()


@router.get("/stats", response_model=schemas.StatsResponse)
async def get_stats(user: User = Depends(get_current_user)):
    """Get user statistics for today and this week.

    Returns:
        StatsResponse: Statistics for today and week
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    # Get today's daily log
    today_log = await DailyLog.filter(
        user_id=user.telegram_id,
        date=today,
    ).first()

    # Today stats
    today_stats = schemas.TodayStatsResponse(
        energy_level=today_log.energy_level if today_log else None,
        steps_assigned=len(today_log.assigned_step_ids) if today_log else 0,
        steps_completed=len(today_log.completed_step_ids) if today_log else 0,
        xp_earned=today_log.xp_earned if today_log else 0,
    )

    # Week stats
    week_logs = await DailyLog.filter(
        user_id=user.telegram_id,
        date__gte=week_start,
        date__lte=today,
    ).all()

    # Count active days (days with at least one completed step)
    active_days = sum(1 for log in week_logs if len(log.completed_step_ids) > 0)

    # Total XP for the week
    total_xp_week = sum(log.xp_earned for log in week_logs)

    # Total completed steps for the week
    total_steps_week = sum(len(log.completed_step_ids) for log in week_logs)

    week_stats = schemas.WeekStatsResponse(
        active_days=active_days,
        total_xp=total_xp_week,
        total_steps=total_steps_week,
    )

    return schemas.StatsResponse(
        today=today_stats,
        week=week_stats,
    )
