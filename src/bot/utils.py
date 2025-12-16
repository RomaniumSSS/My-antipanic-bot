"""
Утилиты для bot handlers.
"""

from aiogram.types import CallbackQuery, InaccessibleMessage, Message


def get_callback_message(callback: CallbackQuery) -> Message:
    """
    Извлечь Message из CallbackQuery с проверкой типа.

    Raises:
        RuntimeError: если message отсутствует или недоступно
    """
    if callback.message is None or isinstance(callback.message, InaccessibleMessage):
        raise RuntimeError("Callback message is not accessible")
    return callback.message

