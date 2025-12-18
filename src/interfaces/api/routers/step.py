"""
Step API router.

Endpoints:
- GET /api/steps/today - Get today's assigned steps
- POST /api/steps/{id}/complete - Mark step as completed
- POST /api/steps/{id}/skip - Skip step with reason
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.use_cases.complete_step import CompleteStepUseCase
from src.core.use_cases.skip_step import SkipStepUseCase
from src.database.models import Step, User
from src.interfaces.api.auth import TelegramUser, get_current_user
from src.interfaces.api.schemas import (
    CompleteStepResponse,
    SkipStepRequest,
    SkipStepResponse,
    StepResponse,
    TodayStepsResponse,
)

router = APIRouter(prefix="/api", tags=["steps"])
logger = logging.getLogger(__name__)


@router.get("/steps/today", response_model=TodayStepsResponse)
async def get_today_steps(
    tg_user: TelegramUser = Depends(get_current_user),
) -> TodayStepsResponse:
    """
    Get today's assigned steps for the user.

    Returns steps that are scheduled for today or have status 'pending'
    and are part of active goals.
    """
    user = await User.filter(telegram_id=tg_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    today = date.today()

    # AICODE-NOTE: Fetch steps scheduled for today from active goals
    # Using prefetch_related to avoid N+1 queries
    steps = (
        await Step.filter(
            scheduled_date=today,
            status__in=["pending", "completed", "skipped"],
            stage__goal__user=user,
            stage__goal__status="active",
        )
        .prefetch_related("stage__goal")
        .order_by("difficulty", "id")
        .all()
    )

    # Count completed steps
    completed_count = sum(1 for s in steps if s.status == "completed")

    # Convert to response models
    step_responses = [StepResponse.model_validate(step) for step in steps]

    return TodayStepsResponse(
        steps=step_responses,
        total_assigned=len(steps),
        completed=completed_count,
    )


@router.post("/steps/{step_id}/complete", response_model=CompleteStepResponse)
async def complete_step(
    step_id: int,
    tg_user: TelegramUser = Depends(get_current_user),
) -> CompleteStepResponse:
    """
    Mark step as completed.

    Awards XP, updates streak, and updates goal/stage progress.
    """
    user = await User.filter(telegram_id=tg_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify step exists and belongs to user
    step = await Step.filter(id=step_id).prefetch_related("stage__goal").first()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step not found",
        )

    # AICODE-NOTE: Verify ownership through goal->user relation
    if step.stage.goal.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Step does not belong to user",
        )

    # Execute use case
    use_case = CompleteStepUseCase()
    result = await use_case.execute(step_id=step_id, user=user)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error_message,
        )

    logger.info(
        f"Step {step_id} completed via API by user {tg_user.id}: +{result.xp_earned} XP"
    )

    return CompleteStepResponse(
        success=True,
        xp_earned=result.xp_earned,
        total_xp=result.total_xp,
        streak_updated=result.streak_updated,
        new_streak=result.new_streak,
    )


@router.post("/steps/{step_id}/skip", response_model=SkipStepResponse)
async def skip_step(
    step_id: int,
    request: SkipStepRequest,
    tg_user: TelegramUser = Depends(get_current_user),
) -> SkipStepResponse:
    """
    Skip step with optional reason.

    Does not award XP but logs the skip reason in DailyLog.
    """
    user = await User.filter(telegram_id=tg_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify step exists and belongs to user
    step = await Step.filter(id=step_id).prefetch_related("stage__goal").first()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step not found",
        )

    # AICODE-NOTE: Verify ownership through goal->user relation
    if step.stage.goal.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Step does not belong to user",
        )

    # Execute use case
    use_case = SkipStepUseCase()
    result = await use_case.execute(
        step_id=step_id, user=user, reason=request.reason or "Не подошло"
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error_message,
        )

    logger.info(
        f"Step {step_id} skipped via API by user {tg_user.id}: {request.reason}"
    )

    return SkipStepResponse(success=True)


