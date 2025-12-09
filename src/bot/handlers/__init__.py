"""Регистрация всех роутеров бота."""

from aiogram import Dispatcher

from .start import router as start_router
from .health import router as health_router
from .onboarding import router as onboarding_router
from .morning import router as morning_router
from .steps import router as steps_router
from .stuck import router as stuck_router
from .evening import router as evening_router
from .weekly import router as weekly_router


def register_routers(dp: Dispatcher) -> None:
    """Подключить все роутеры в диспетчер."""
    dp.include_routers(
        start_router,
        health_router,
        onboarding_router,
        morning_router,
        steps_router,
        stuck_router,
        evening_router,
        weekly_router,
    )
