"""Регистрация всех роутеров бота."""

from aiogram import Dispatcher

from .evening import router as evening_router
from .morning import router as morning_router
from .onboarding import router as onboarding_router
from .start import router as start_router
from .steps import router as steps_router
from .stuck import router as stuck_router


def register_routers(dp: Dispatcher) -> None:
    """Подключить все роутеры в диспетчер."""
    dp.include_routers(
        start_router,
        onboarding_router,
        morning_router,
        steps_router,
        stuck_router,
        evening_router,
    )
