"""
MicroHit API router.

Endpoints:
- POST /api/microhit - Generate multiple micro-action variants for stuck state

Uses resolve_stuck_use_case for consistency with bot flow.
Plan 004: Passes user/daily_log for adaptive tone.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.use_cases.resolve_stuck import resolve_stuck_use_case
from src.database.models import Step, User
from src.interfaces.api.auth import TelegramUser, get_current_user
from src.interfaces.api.schemas import (
    MicroHitRequest,
    MicroHitResponse,
    MicroHitVariant,
    StepResponse,
)
from src.storage import daily_log_repo

router = APIRouter(prefix="/api", tags=["microhit"])


@router.post("/microhit", response_model=MicroHitResponse)
async def create_microhit(
    request: MicroHitRequest,
    tg_user: TelegramUser = Depends(get_current_user),
) -> MicroHitResponse:
    """
    Generate multiple micro-action variants for when user is stuck.

    Uses resolve_stuck_use_case to generate 2-3 different approaches
    to unblock the user. Returns all variants for user to choose from.

    Expected blocker_type values:
    - fear: страшно начать
    - unclear: не знаю с чего начать
    - no_time: нет времени
    - no_energy: нет сил
    """
    user = await User.filter(telegram_id=tg_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get the step and verify ownership
    step = await Step.filter(id=request.step_id).prefetch_related("stage__goal").first()

    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step not found",
        )

    # Verify the step belongs to user's goal
    if step.stage.goal.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Step does not belong to user",
        )

    # Get daily_log for adaptive tone (plan 004)
    daily_log = await daily_log_repo.get_or_create_daily_log(user, date.today())

    # Generate multiple microhit variants using use-case (with adaptive tone)
    result = await resolve_stuck_use_case.generate_microhit_options(
        step_title=step.title,
        blocker_type=request.blocker_type,
        details=request.blocker_text or "",
        user=user,
        daily_log=daily_log,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "Failed to generate microhit variants",
        )

    # Convert to response format
    variants = [
        MicroHitVariant(index=opt.index, text=opt.text) for opt in (result.options or [])
    ]

    return MicroHitResponse(
        variants=variants,
        original_step=StepResponse.model_validate(step),
        blocker_type=request.blocker_type,
    )
