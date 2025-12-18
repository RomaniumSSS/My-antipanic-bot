"""
Fallback handler — обработка неизвестных сообщений.

AICODE-NOTE: Добавлено по плану 005 (Phase 4).
Должен быть зарегистрирован ПОСЛЕДНИМ в роутерах, чтобы сработать
только если никакой другой handler не обработал сообщение.
"""

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="fallback")


@router.message()
async def fallback_handler(message: Message, state: FSMContext) -> None:
    """
    Fallback для неизвестных сообщений.
    
    Срабатывает когда:
    - Пользователь прислал текст, который не обработал ни один другой handler
    - Пользователь в FSM состоянии, но прислал неожиданный текст
    """
    current_state = await state.get_state()
    
    if current_state:
        # Пользователь в FSM состоянии, но прислал неожиданное сообщение
        logger.info(
            f"Fallback: user {message.from_user.id if message.from_user else 'unknown'} "
            f"in state {current_state}, message: {message.text[:50] if message.text else 'no text'}"
        )
        await message.answer(
            "Не понял. Используй /cancel чтобы выйти или /help для списка команд.",
            reply_markup=main_menu_keyboard(),
        )
    else:
        # Пользователь не в FSM состоянии, показываем список команд
        logger.info(
            f"Fallback: user {message.from_user.id if message.from_user else 'unknown'} "
            f"no state, message: {message.text[:50] if message.text else 'no text'}"
        )
        await message.answer(
            "🤔 Не понял команду.\n\n"
            "*Основные команды:*\n"
            "• /morning — план на день\n"
            "• /stuck — помощь при ступоре\n"
            "• /evening — итоги дня\n"
            "• /status — прогресс\n\n"
            "Используй /help для полного списка.",
            reply_markup=main_menu_keyboard(),
        )

