"""
Клавиатуры для Antipanic Bot.

Все клавиатуры используют CallbackData фабрики из src.bot.callbacks.data.
НЕ используй raw строки для callback_data!
"""

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

from src.bot.callbacks.data import (
    EnergyCallback,
    SimpleEnergyCallback,
    EnergyLevel,
    ConfirmCallback,
    BlockerCallback,
    RatingCallback,
    StepCallback,
    MicrohitFeedbackCallback,
    QuickStepCallback,
    GoalSelectCallback,
    TensionCallback,
    DeepenCallback,
    DeepenAction,
    BlockerType,
    ConfirmAction,
    StepAction,
    MicrohitFeedbackAction,
    QuickStepAction,
)


def energy_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора энергии 1-10 (legacy)."""
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=EnergyCallback(value=i))
    builder.adjust(5, 5)
    return builder.as_markup()


def simple_energy_keyboard() -> InlineKeyboardMarkup:
    """
    Упрощённая клавиатура энергии — 3 уровня.
    Снижает когнитивную нагрузку (Hick's Law).
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="😴 Мало сил",
        callback_data=SimpleEnergyCallback(level=EnergyLevel.low),
    )
    builder.button(
        text="😐 Норм",
        callback_data=SimpleEnergyCallback(level=EnergyLevel.medium),
    )
    builder.button(
        text="⚡ Бодрый",
        callback_data=SimpleEnergyCallback(level=EnergyLevel.high),
    )
    builder.adjust(3)
    return builder.as_markup()


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение."""
    builder = InlineKeyboardBuilder()
    cb_yes = ConfirmCallback(action=ConfirmAction.yes)
    cb_edit = ConfirmCallback(action=ConfirmAction.edit)
    builder.button(text="✅ Ок", callback_data=cb_yes)
    builder.button(text="✏️ Изменить", callback_data=cb_edit)
    builder.adjust(2)
    return builder.as_markup()


def confirm_with_cancel_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение с отменой."""
    builder = InlineKeyboardBuilder()
    cb_yes = ConfirmCallback(action=ConfirmAction.yes)
    cb_edit = ConfirmCallback(action=ConfirmAction.edit)
    cb_cancel = ConfirmCallback(action=ConfirmAction.cancel)
    builder.button(text="✅ Ок", callback_data=cb_yes)
    builder.button(text="✏️ Изменить", callback_data=cb_edit)
    builder.button(text="❌ Отмена", callback_data=cb_cancel)
    builder.adjust(2, 1)
    return builder.as_markup()


def blocker_keyboard() -> InlineKeyboardMarkup:
    """Причина застревания."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="😨 Страшно",
        callback_data=BlockerCallback(type=BlockerType.fear),
    )
    builder.button(
        text="🤷 Не знаю с чего",
        callback_data=BlockerCallback(type=BlockerType.unclear),
    )
    builder.button(
        text="⏰ Нет времени",
        callback_data=BlockerCallback(type=BlockerType.no_time),
    )
    builder.button(
        text="😴 Нет сил",
        callback_data=BlockerCallback(type=BlockerType.no_energy),
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


def step_actions_keyboard(step_id: int) -> InlineKeyboardMarkup:
    """Действия с конкретным шагом: Сделал / Пропустить / Застрял."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Сделал",
        callback_data=StepCallback(action=StepAction.done, step_id=step_id),
    )
    builder.button(
        text="⏭ Пропустить",
        callback_data=StepCallback(action=StepAction.skip, step_id=step_id),
    )
    builder.button(
        text="🆘 Застрял",
        callback_data=StepCallback(action=StepAction.stuck, step_id=step_id),
    )
    builder.adjust(2, 1)
    return builder.as_markup()


def steps_list_keyboard(step_ids: list[int]) -> InlineKeyboardMarkup:
    """
    Клавиатура для списка шагов с кнопками действий.
    Показывает номер шага и кнопки для каждого.
    """
    builder = InlineKeyboardBuilder()
    for i, step_id in enumerate(step_ids, start=1):
        cb_done = StepCallback(action=StepAction.done, step_id=step_id)
        cb_stuck = StepCallback(action=StepAction.stuck, step_id=step_id)
        builder.button(text=f"✅ Шаг {i}", callback_data=cb_done)
        builder.button(text="🆘", callback_data=cb_stuck)
    builder.adjust(2)
    return builder.as_markup()


def yes_no_keyboard() -> InlineKeyboardMarkup:
    """Простое подтверждение Да/Нет."""
    builder = InlineKeyboardBuilder()
    cb_yes = ConfirmCallback(action=ConfirmAction.yes)
    cb_no = ConfirmCallback(action=ConfirmAction.cancel)
    builder.button(text="✅ Да", callback_data=cb_yes)
    builder.button(text="❌ Нет", callback_data=cb_no)
    builder.adjust(2)
    return builder.as_markup()


def microhit_feedback_keyboard(
    step_id: int | None, blocker: BlockerType
) -> InlineKeyboardMarkup:
    """Кнопки реакции на микро-удар."""
    builder = InlineKeyboardBuilder()
    sid = step_id or 0  # 0 = без привязки к шагу
    builder.button(
        text="✅ Сделаю",
        callback_data=MicrohitFeedbackCallback(
            action=MicrohitFeedbackAction.do, step_id=sid, blocker=blocker
        ),
    )
    builder.button(
        text="🆘 Нужна подсказка",
        callback_data=MicrohitFeedbackCallback(
            action=MicrohitFeedbackAction.more, step_id=sid, blocker=blocker
        ),
    )
    builder.button(
        text="✏️ Другое",
        callback_data=MicrohitFeedbackCallback(
            action=MicrohitFeedbackAction.other, step_id=sid, blocker=blocker
        ),
    )
    builder.adjust(1, 2)
    return builder.as_markup()


def low_energy_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для пользователей с низкой энергией."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⚡ Шаг на 2 минуты",
        callback_data=QuickStepCallback(action=QuickStepAction.quick),
    )
    builder.button(
        text="Оставить как есть",
        callback_data=QuickStepCallback(action=QuickStepAction.keep),
    )
    builder.adjust(1, 1)
    return builder.as_markup()


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню с ключевыми командами."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Утро"), KeyboardButton(text="Застрял")],
            [KeyboardButton(text="Вечер"), KeyboardButton(text="Статус")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Утро — план дня, Застрял — быстрая помощь",
    )


def goal_select_keyboard(goals: list) -> InlineKeyboardMarkup:
    """Выбор цели/темы для утреннего анти-паралич потока."""
    builder = InlineKeyboardBuilder()
    for goal in goals:
        builder.button(
            text=f"🎯 {getattr(goal, 'title', 'Цель')}",
            callback_data=GoalSelectCallback(goal_id=getattr(goal, "id", 0)),
        )
    builder.adjust(1)
    return builder.as_markup()


def tension_keyboard() -> InlineKeyboardMarkup:
    """Шкала напряжения 0-10 (шаг 2) для лёгкого выбора."""
    builder = InlineKeyboardBuilder()
    for value in (0, 2, 4, 6, 8, 10):
        builder.button(text=str(value), callback_data=TensionCallback(value=value))
    builder.adjust(6)
    return builder.as_markup()


def deepen_keyboard() -> InlineKeyboardMarkup:
    """Кнопки после оценки: углубиться или завершить."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🚀 Ещё 15–30 минут",
        callback_data=DeepenCallback(action=DeepenAction.more),
    )
    builder.button(
        text="✅ Хватит, сохранить прогресс",
        callback_data=DeepenCallback(action=DeepenAction.finish),
    )
    builder.adjust(1, 1)
    return builder.as_markup()
