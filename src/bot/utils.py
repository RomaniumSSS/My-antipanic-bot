"""
Утилиты для bot handlers.
"""

import logging
import re
from functools import wraps
from typing import Any, Callable, Coroutine

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message

logger = logging.getLogger(__name__)


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


def prevent_double_click(
    feedback_message: str = "⏳ Уже обрабатываю, подожди секунду..."
) -> Callable[
    [Callable[..., Coroutine[Any, Any, None]]],
    Callable[..., Coroutine[Any, Any, None]],
]:
    """
    Декоратор для защиты от повторных кликов на callback buttons.

    Устанавливает флаг `processing=True` в FSM state перед выполнением handler'а
    и сбрасывает его в `False` после завершения. Если handler вызывается повторно
    во время обработки, пользователь получает feedback сообщение.

    Args:
        feedback_message: Сообщение для пользователя при повторном клике

    Returns:
        Decorator function

    Usage:
        @router.callback_query(StepCallback.filter(F.action == StepAction.done))
        @prevent_double_click()
        async def step_done(callback: CallbackQuery, state: FSMContext) -> None:
            ...

    AICODE-NOTE: Добавлено в Plan 005 для защиты от race conditions и
    дублирования операций (двойное начисление XP, создание дубликатов шагов).
    """

    def decorator(
        handler: Callable[..., Coroutine[Any, Any, None]]
    ) -> Callable[..., Coroutine[Any, Any, None]]:
        @wraps(handler)
        async def wrapper(*args: Any, **kwargs: Any) -> None:
            # Находим CallbackQuery и FSMContext в аргументах
            callback: CallbackQuery | None = None
            state: FSMContext | None = None

            for arg in args:
                if isinstance(arg, CallbackQuery):
                    callback = arg
                elif isinstance(arg, FSMContext):
                    state = arg

            # Проверяем kwargs если не нашли в args
            if not callback:
                callback = kwargs.get("callback")
            if not state:
                state = kwargs.get("state")

            if not callback or not state:
                # Если нет callback или state, просто выполняем handler
                # (декоратор применён к неподходящему handler'у)
                logger.warning(
                    f"prevent_double_click applied to handler {handler.__name__} "
                    "without CallbackQuery or FSMContext - skipping protection"
                )
                await handler(*args, **kwargs)
                return

            # Проверяем флаг processing в FSM state
            data = await state.get_data()
            if data.get("processing"):
                # Уже обрабатываем - показываем feedback и игнорируем клик
                logger.info(
                    f"Double click prevented in {handler.__name__} "
                    f"for user {callback.from_user.id if callback.from_user else 'unknown'}"
                )
                await callback.answer(feedback_message, show_alert=False)
                return

            # Устанавливаем флаг processing
            await state.update_data(processing=True)

            try:
                # Выполняем handler
                await handler(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"Error in handler {handler.__name__}: {e}"
                )
                # Пробрасываем исключение дальше, но сначала сбросим флаг
                raise
            finally:
                # Сбрасываем флаг processing в любом случае
                await state.update_data(processing=False)

        return wrapper

    return decorator

