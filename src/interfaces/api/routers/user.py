"""
User API router.

Endpoints:
- GET /api/me - Get current user profile
"""

from fastapi import APIRouter, Depends

from src.database.models import User
from src.interfaces.api.auth import TelegramUser, get_current_user
from src.interfaces.api.schemas import UserResponse

router = APIRouter(prefix="/api", tags=["user"])


@router.get("/me", response_model=UserResponse)
async def get_me(tg_user: TelegramUser = Depends(get_current_user)) -> UserResponse:
    """
    Get current user profile.

    Returns user data including gamification stats and settings.
    Creates user if not exists (auto-registration from TMA).
    """
    # Try to find existing user
    user = await User.filter(telegram_id=tg_user.id).first()

    if not user:
        # Auto-create user from TMA (same as bot's /start)
        user = await User.create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
        )

    return UserResponse.model_validate(user)
