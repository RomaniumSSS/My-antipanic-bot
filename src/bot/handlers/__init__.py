"""Регистрация всех роутеров бота."""

from aiogram import Dispatcher

from .start import router as start_router
from .health import router as health_router


def register_routers(dp: Dispatcher) -> None:
    """Подключить все роутеры в диспетчер."""
    dp.include_routers(
        start_router,
        health_router,
    )
