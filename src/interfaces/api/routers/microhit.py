"""
MicroHit API router.

Endpoints:
- POST /api/microhit - Generate micro-action for stuck state
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.database.models import Step, User
from src.interfaces.api.auth import TelegramUser, get_current_user
from src.interfaces.api.schemas import MicroHitRequest, MicroHitResponse, StepResponse
from src.services.ai import ai_service

router = APIRouter(prefix="/api", tags=["microhit"])


@router.post("/microhit", response_model=MicroHitResponse)
async def create_microhit(
    request: MicroHitRequest,
    tg_user: TelegramUser = Depends(get_current_user),
) -> MicroHitResponse:
    """
    Generate a micro-action for when user is stuck.

    Uses AI to break down the step into a 2-5 minute micro-action
    based on the current blocker.
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

    # Generate micro-action using AI service
    # AICODE-NOTE: Reusing existing AI service from bot
    # get_microhit expects blocker_type: fear, unclear, no_time, no_energy
    # Default to "unclear" if no blocker specified
    micro_action = await ai_service.get_microhit(
        step_title=step.title,
        blocker_type="unclear",
        details=request.blocker_text or "",
    )

    return MicroHitResponse(
        micro_action=micro_action,
        original_step=StepResponse.model_validate(step),
        estimated_minutes=3,  # Micro-hits are always ~3 minutes
    )
