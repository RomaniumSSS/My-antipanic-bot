"""
Утилиты для bot handlers.
"""

import re

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


def escape_markdown(text: str) -> str:
    """
    Экранировать специальные символы Markdown для безопасного вывода в Telegram.

    Экранирует символы: _ * [ ] ( ) ~ ` > # + - = | { }
    Это предотвращает ошибки парсинга entities когда в user-generated content
    (названия шагов, целей, этапов) есть специальные символы.

    Args:
        text: Текст для экранирования

    Returns:
        Текст с экранированными markdown символами
    """
    # Специальные символы Markdown v2 (используется в Telegram)
    special_chars = r'_*[]()~`>#+-=|{}'
    return re.sub(f'([{re.escape(special_chars)}])', r'\\\1', text)

