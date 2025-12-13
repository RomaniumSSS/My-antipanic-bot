"""
Error Handling Middleware.

Перехватывает исключения в хендлерах и логирует их.
Отправляет пользователю дружелюбное сообщение вместо молчания.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import CallbackQuery, Message, TelegramObject

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseMiddleware):
    """
    Middleware для обработки ошибок.

    Использование:
        dp.message.middleware(ErrorHandlingMiddleware())
        dp.callback_query.middleware(ErrorHandlingMiddleware())
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except SkipHandler:
            # Пропускаем без логов и ответов — это штатный сигнал роутинга.
            raise
        except Exception as e:
            # Логируем полную ошибку с трейсбеком
            logger.exception(f"Error handling {type(event).__name__}: {e}")

            # Отправляем пользователю дружелюбное сообщение
            error_message = "❌ Произошла ошибка. Попробуй ещё раз или напиши /start"

            try:
                if isinstance(event, Message):
                    await event.answer(error_message)
                elif isinstance(event, CallbackQuery):
                    await event.message.answer(error_message)
                    # Всегда отвечаем на callback, чтобы убрать часики
                    await event.answer("Ошибка обработки")
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")

            # Не пробрасываем исключение дальше, чтобы бот не крашился
            return None
