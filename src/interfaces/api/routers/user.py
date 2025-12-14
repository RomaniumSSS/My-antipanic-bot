"""User profile API endpoints."""

from fastapi import APIRouter, Depends

from src.database.models import User
from src.interfaces.api import schemas
from src.interfaces.api.auth import get_current_user

router = APIRouter()


@router.get("/me", response_model=schemas.UserProfileResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile.

    Returns:
        UserProfileResponse: User profile data with XP, level, streak
    """
    return schemas.UserProfileResponse(
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        xp=user.xp,
        level=user.level,
        streak_days=user.streak_days,
        timezone_offset=user.timezone_offset,
    )
