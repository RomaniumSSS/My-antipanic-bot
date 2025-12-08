"""
Access Control Middleware.

Проверяет, есть ли пользователь в whitelist (ALLOWED_USER_IDS).
Если whitelist пустой — пропускает всех.
"""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from src.config import config


class AccessMiddleware(BaseMiddleware):
    """
    Middleware для проверки доступа по whitelist.
    
    Использование:
        dp.message.middleware(AccessMiddleware())
        dp.callback_query.middleware(AccessMiddleware())
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Если whitelist пустой — пропускаем всех
        if not config.ALLOWED_USER_IDS:
            return await handler(event, data)

        # Извлекаем user_id из события
        user_id = self._get_user_id(event)

        # Проверяем доступ
        if user_id and user_id in config.ALLOWED_USER_IDS:
            return await handler(event, data)

        # Молча игнорируем неразрешённых пользователей
        # AICODE-NOTE: Не отвечаем неразрешённым пользователям, чтобы не раскрывать
        # существование бота случайным людям во время альфа-тестирования
        return None

    @staticmethod
    def _get_user_id(event: TelegramObject) -> int | None:
        """Извлечь user_id из события."""
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        return None

