"""Регистрация всех роутеров бота."""

from aiogram import Dispatcher

from .evening import router as evening_router
from .fallback import router as fallback_router
from .manage_goals import router as manage_goals_router
from .morning import router as morning_router
from .onboarding import router as onboarding_router
from .start import router as start_router
from .steps import router as steps_router
from .stuck import router as stuck_router


def register_routers(dp: Dispatcher) -> None:
    """
    Подключить все роутеры в диспетчер.
    
    AICODE-NOTE: fallback_router должен быть ПОСЛЕДНИМ (Plan 005, Phase 4).
    Он срабатывает только если никакой другой handler не обработал сообщение.
    """
    dp.include_routers(
        start_router,
        manage_goals_router,  # Регистрируем раньше, чтобы /goals имел приоритет
        onboarding_router,
        morning_router,
        steps_router,
        stuck_router,
        evening_router,
        fallback_router,  # ПОСЛЕДНИМ - fallback для неизвестных сообщений
    )
