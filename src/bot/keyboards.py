"""
Клавиатуры для Antipanic Bot.

Все клавиатуры используют CallbackData фабрики из src.bot.callbacks.data.
НЕ используй raw строки для callback_data!
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from src.bot.callbacks.data import (
    EnergyCallback,
    ConfirmCallback,
    BlockerCallback,
    RatingCallback,
    BlockerType,
    ConfirmAction,
)


def energy_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора энергии 1-10."""
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=EnergyCallback(value=i))
    builder.adjust(5, 5)
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Ок",
        callback_data=ConfirmCallback(action=ConfirmAction.yes)
    )
    builder.button(
        text="✏️ Изменить",
        callback_data=ConfirmCallback(action=ConfirmAction.edit)
    )
    builder.adjust(2)
    return builder.as_markup()


def confirm_with_cancel_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение с отменой."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Ок",
        callback_data=ConfirmCallback(action=ConfirmAction.yes)
    )
    builder.button(
        text="✏️ Изменить",
        callback_data=ConfirmCallback(action=ConfirmAction.edit)
    )
    builder.button(
        text="❌ Отмена",
        callback_data=ConfirmCallback(action=ConfirmAction.cancel)
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def blocker_keyboard() -> InlineKeyboardMarkup:
    """Причина застревания."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="😨 Страшно",
        callback_data=BlockerCallback(type=BlockerType.fear)
    )
    builder.button(
        text="🤷 Не знаю с чего",
        callback_data=BlockerCallback(type=BlockerType.unclear)
    )
    builder.button(
        text="⏰ Нет времени",
        callback_data=BlockerCallback(type=BlockerType.no_time)
    )
    builder.button(
        text="😴 Нет сил",
        callback_data=BlockerCallback(type=BlockerType.no_energy)
    )
    builder.adjust(2, 2)
    return builder.as_markup()


def rating_keyboard() -> InlineKeyboardMarkup:
    """Оценка дня 1-5."""
    builder = InlineKeyboardBuilder()
    emojis = ["😫", "😕", "😐", "🙂", "😊"]
    for i, emoji in enumerate(emojis, start=1):
        builder.button(text=emoji, callback_data=RatingCallback(value=i))
    builder.adjust(5)
    return builder.as_markup()
