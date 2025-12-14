"""Development-only endpoints without authentication.

IMPORTANT: These endpoints should ONLY be used in development.
Remove or disable this router in production!
"""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from src.core.use_cases.complete_step import CompleteStepUseCase
from src.core.use_cases.resolve_stuck import resolve_stuck_use_case
from src.database.models import DailyLog, Goal, Stage, Step, User
from src.interfaces.api import schemas
from src.storage import goal_repo, step_repo

router = APIRouter(prefix="/dev", tags=["development"])


@router.get("/users")
async def list_users():
    """List all users in database (for finding telegram_id)."""
    users = await User.all().limit(10)
    return [
        {
            "telegram_id": u.telegram_id,
            "username": u.username,
            "first_name": u.first_name,
            "xp": u.xp,
            "level": u.level,
        }
        for u in users
    ]


@router.get("/me")
async def dev_get_me(telegram_id: int = Query(..., description="User's telegram_id")):
    """Get user profile without auth (dev only)."""
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User {telegram_id} not found. Start the bot with /start first.",
        )

    return schemas.UserProfileResponse(
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        xp=user.xp,
        level=user.level,
        streak_days=user.streak_days,
        timezone_offset=user.timezone_offset,
    )


@router.get("/goals")
async def dev_get_goals(telegram_id: int = Query(...)):
    """Get active goal without auth (dev only)."""
    goal = await goal_repo.get_active_goal(telegram_id)
    if not goal:
        raise HTTPException(status_code=404, detail="No active goal")

    stage = await goal_repo.get_active_stage(goal.id)

    return schemas.GoalResponse(
        id=goal.id,
        title=goal.title,
        current_stage=stage.title if stage else None,
        progress=stage.progress if stage else 0,
        deadline=goal.deadline.isoformat() if goal.deadline else None,
    )


@router.post("/microhit/generate")
async def dev_generate_microhit(
    telegram_id: int = Query(...),
    step_title: str = Query(default="Начать работу"),
    blocker_type: str = Query(default="fear"),
):
    """Generate microhit without auth (dev only)."""
    # Get user
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get active goal and stage
    goal = await goal_repo.get_active_goal(telegram_id)
    if not goal:
        raise HTTPException(status_code=404, detail="No active goal")

    stage = await goal_repo.get_active_stage(goal.id)
    if not stage:
        raise HTTPException(status_code=404, detail="No active stage")

    # Generate microhit options
    try:
        result = await resolve_stuck_use_case.generate_microhit_options(
            step_title=step_title,
            blocker_type=blocker_type,
            details="",
            count=3,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate: {str(e)}")

    if not result.options:
        raise HTTPException(status_code=500, detail="No options generated")

    # Create step
    step = await step_repo.create_step(
        stage_id=stage.id,
        title=step_title,
        difficulty="easy",
        estimated_minutes=5,
        xp_reward=10,
        scheduled_date=date.today(),
        status="pending",
    )

    options = [
        schemas.MicrohitOption(index=i, text=opt.text)
        for i, opt in enumerate(result.options)
    ]

    return schemas.MicrohitGenerateResponse(
        options=options,
        step_id=step.id,
    )


@router.post("/microhit/complete")
async def dev_complete_microhit(
    telegram_id: int = Query(...),
    step_id: int = Query(...),
):
    """Complete microhit without auth (dev only)."""
    # Verify step exists and belongs to user
    step = await Step.filter(id=step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    stage = await step_repo.get_stage(step.stage_id)
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")

    goal = await goal_repo.get_goal_by_id(stage.goal_id)
    if not goal or goal.user_id != telegram_id:
        raise HTTPException(status_code=403, detail="Not your step")

    # Complete step
    use_case = CompleteStepUseCase()
    try:
        result = await use_case.execute(telegram_id, step_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")

    return schemas.MicrohitCompleteResponse(
        xp_earned=result.xp_earned,
        total_xp=result.new_total_xp,
        streak_days=result.streak_days,
        level=result.new_level,
    )


@router.get("/stats")
async def dev_get_stats(telegram_id: int = Query(...)):
    """Get stats without auth (dev only)."""
    user = await User.filter(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from datetime import timedelta

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    # Today
    today_log = await DailyLog.filter(user_id=telegram_id, date=today).first()
    today_stats = schemas.TodayStatsResponse(
        energy_level=today_log.energy_level if today_log else None,
        steps_assigned=len(today_log.assigned_step_ids) if today_log else 0,
        steps_completed=len(today_log.completed_step_ids) if today_log else 0,
        xp_earned=today_log.xp_earned if today_log else 0,
    )

    # Week
    week_logs = await DailyLog.filter(
        user_id=telegram_id, date__gte=week_start, date__lte=today
    ).all()

    active_days = sum(1 for log in week_logs if len(log.completed_step_ids) > 0)
    total_xp_week = sum(log.xp_earned for log in week_logs)
    total_steps_week = sum(len(log.completed_step_ids) for log in week_logs)

    week_stats = schemas.WeekStatsResponse(
        active_days=active_days,
        total_xp=total_xp_week,
        total_steps=total_steps_week,
    )

    return schemas.StatsResponse(today=today_stats, week=week_stats)


@router.get("/history")
async def dev_get_history(
    telegram_id: int = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get history without auth (dev only)."""
    goals = await Goal.filter(user_id=telegram_id).all()
    goal_ids = [goal.id for goal in goals]

    stages = await Stage.filter(goal_id__in=goal_ids).all()
    stage_ids = [stage.id for stage in stages]

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
