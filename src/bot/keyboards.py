"""
Клавиатуры для Antipanic Bot.
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup


def energy_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора энергии 1-10."""
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=f"energy:{i}")
    builder.adjust(5, 5)
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ок", callback_data="confirm:yes")
    builder.button(text="✏️ Изменить", callback_data="confirm:edit")
    builder.adjust(2)
    return builder.as_markup()


def blocker_keyboard() -> InlineKeyboardMarkup:
    """Причина застревания."""
    builder = InlineKeyboardBuilder()
    builder.button(text="😨 Страшно", callback_data="blocker:fear")
    builder.button(text="🤷 Не знаю с чего", callback_data="blocker:unclear")
    builder.button(text="⏰ Нет времени", callback_data="blocker:no_time")
    builder.button(text="😴 Нет сил", callback_data="blocker:no_energy")
    builder.adjust(2, 2)
    return builder.as_markup()
