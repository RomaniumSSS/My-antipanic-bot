"""Microhit API endpoints (stuck resolution)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from src.core.use_cases.complete_step import CompleteStepUseCase
from src.core.use_cases.resolve_stuck import resolve_stuck_use_case
from src.database.models import Step, User
from src.interfaces.api import schemas
from src.interfaces.api.auth import get_current_user
from src.storage import goal_repo, step_repo

router = APIRouter()


@router.post("/microhit/generate", response_model=schemas.MicrohitGenerateResponse)
async def generate_microhit(
    request: schemas.MicrohitGenerateRequest,
    user: User = Depends(get_current_user),
):
    """Generate microhit options for a stuck step.

    Args:
        request: Microhit generation request with blocker info
        user: Authenticated user

    Returns:
        MicrohitGenerateResponse: List of microhit options and step ID

    Raises:
        HTTPException: If no active goal or generation fails
    """
    # Get active goal and stage
    goal = await goal_repo.get_active_goal(user.telegram_id)
    if not goal:
        raise HTTPException(
            status_code=404,
            detail="No active goal. Please create a goal in the bot first.",
        )

    stage = await goal_repo.get_active_stage(goal.id)
    if not stage:
        raise HTTPException(
            status_code=404,
            detail="No active stage. Please create stages for your goal.",
        )

    # Generate microhit options using use-case
    try:
        result = await resolve_stuck_use_case.generate_microhit_options(
            step_title=request.step_title,
            blocker_type=request.blocker_type,
            details=request.details or "",
            count=3,  # Generate 3 options
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate microhit: {str(e)}",
        )

    # Create a step for tracking (use first option as title)
    if not result.options:
        raise HTTPException(
            status_code=500,
            detail="No microhit options generated",
        )

    # Create step with the stuck context
    step = await step_repo.create_step(
        stage_id=stage.id,
        title=request.step_title,
        difficulty="easy",
        estimated_minutes=5,
        xp_reward=10,
        scheduled_date=date.today(),
        status="pending",
    )

    # Format response
    options = [
        schemas.MicrohitOption(index=i, text=opt.text)
        for i, opt in enumerate(result.options)
    ]

    return schemas.MicrohitGenerateResponse(
        options=options,
        step_id=step.id,
    )


@router.post("/microhit/complete", response_model=schemas.MicrohitCompleteResponse)
async def complete_microhit(
    request: schemas.MicrohitCompleteRequest,
    user: User = Depends(get_current_user),
):
    """Complete a microhit step.

    Args:
        request: Complete request with step ID
        user: Authenticated user

    Returns:
        MicrohitCompleteResponse: XP earned and updated stats

    Raises:
        HTTPException: If step not found or completion fails
    """
    # Verify step belongs to user
    step = await Step.filter(id=request.step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    # Get stage to verify ownership
    stage = await step_repo.get_stage(step.stage_id)
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")

    goal = await goal_repo.get_goal_by_id(stage.goal_id)
    if not goal or goal.user_id != user.telegram_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to complete this step",
        )

    # Complete step using use-case
    use_case = CompleteStepUseCase()
    try:
        result = await use_case.execute(user.telegram_id, request.step_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete step: {str(e)}",
        )

    return schemas.MicrohitCompleteResponse(
        xp_earned=result.xp_earned,
        total_xp=result.new_total_xp,
        streak_days=result.streak_days,
        level=result.new_level,
    )
