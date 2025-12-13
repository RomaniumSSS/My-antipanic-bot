"""
Evening handlers — вечерний итог дня.

Flow (упрощённый для TMA миграции):
1. /evening → показ шагов с отметками
2. Предложение отметить неотмеченные
3. Обновление streak, XP → завершение

AICODE-NOTE: Упрощено для Этапа 1.4 TMA миграции.
Убрана оценка дня (rating 1-5) и мотивационные сообщения.
Теперь: показ шагов → отметка → +XP → streak → готово.
"""

import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import main_menu_keyboard, steps_list_keyboard
from src.bot.states import EveningStates
from src.database.models import DailyLog, Step, User

logger = logging.getLogger(__name__)

router = Router()


def update_streak(user: User, today: date) -> None:
    """Пересчитать streak с учётом сегодняшней даты."""
    yesterday = today - timedelta(days=1)
    if user.streak_last_date == yesterday:
        user.streak_days += 1
    elif user.streak_last_date != today:
        user.streak_days = 1
    user.streak_last_date = today


@router.message(F.text.casefold().in_(("вечер", "/evening")))
async def evening_from_menu(message: Message, state: FSMContext) -> None:
    """Поддержка кнопки меню для запуска /evening."""
    await cmd_evening(message, state)


@router.message(Command("evening"))
async def cmd_evening(message: Message, state: FSMContext) -> None:
    """Начало вечернего итога."""
    if not message.from_user:
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        await message.answer("Сначала напиши /start")
        return

    today = date.today()
    daily_log = await DailyLog.get_or_none(user=user, date=today)

    if not daily_log or not daily_log.assigned_step_ids:
        await state.clear()
        await message.answer(
            "Сегодня ещё не было старта дня. "
            "Сначала сделай короткий утренний чек-ин через кнопку «Утро».",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Получаем шаги
    steps = await Step.filter(id__in=daily_log.assigned_step_ids)

    # Считаем статистику
    completed = [s for s in steps if s.status == "completed"]
    pending = [s for s in steps if s.status == "pending"]

    # Формируем текст
    steps_text = ""
    for s in steps:
        if s.status == "completed":
            icon = "✅"
        elif s.status == "skipped":
            icon = "⏭"
        else:
            icon = "⬜"
        steps_text += f"{icon} {s.title}\n"

    # AICODE-NOTE: Упрощённый флоу без оценки дня
    if pending:
        await message.answer(
            f"🌙 *Вечерний итог*\n\n"
            f"*Шаги дня:*\n{steps_text}\n"
            f"Есть неотмеченные шаги. Отметь их или нажми кнопку ниже для завершения:",
            reply_markup=steps_list_keyboard([s.id for s in pending]),
        )
        await state.set_state(EveningStates.marking_done)
    else:
        # Все отмечены — сразу завершаем день
        await finish_day(message, user, steps, completed, daily_log, state)


async def finish_day(
    message: Message,
    user: User,
    steps: list,
    completed: list,
    daily_log: DailyLog,
    state: FSMContext,
) -> None:
    """
    Завершение дня (упрощённое).

    AICODE-NOTE: Убрана оценка дня и мотивационные сообщения.
    Теперь сразу показываем итог: шаги → XP → streak.
    """
    total = len(steps)
    done = len(completed)
    xp_earned = daily_log.xp_earned or 0

    steps_text = ""
    for s in steps:
        if s.status == "completed":
            icon = "✅"
        elif s.status == "skipped":
            icon = "⏭"
        else:
            icon = "⬜"
        steps_text += f"{icon} {s.title}\n"

    # Обновляем streak
    today = date.today()
    update_streak(user, today)
    await user.save()

    await state.clear()

    # Формируем итоговое сообщение
    streak_text = ""
    if user.streak_days >= 3:
        streak_text = f"\n🔥 *Streak: {user.streak_days} дней подряд!*"
    elif user.streak_days > 0:
        streak_text = f"\n🔥 Streak: {user.streak_days}"

    await message.answer(
        f"🌙 *День завершён!*\n\n"
        f"{steps_text}\n"
        f"📊 Выполнено: {done}/{total}\n"
        f"⭐ XP за день: +{xp_earned}\n"
        f"⭐ Всего XP: {user.xp}{streak_text}\n\n"
        "До завтра! Напишу утром 🌅",
        reply_markup=main_menu_keyboard(),
    )

    logger.info(
        f"Evening completed for user {user.telegram_id}: "
        f"completed={done}/{total}, streak={user.streak_days}"
    )


# AICODE-NOTE: Удалён обработчик process_rating после упрощения вечернего флоу.
# Теперь день завершается сразу через функцию finish_day() без оценки.


@router.message(Command("finish_day"))
async def cmd_finish_day(message: Message, state: FSMContext) -> None:
    """
    Альтернативная команда для завершения дня (пропуск неотмеченных).

    AICODE-NOTE: Обновлена после упрощения - теперь сразу завершаем день без оценки.
    """
    if not message.from_user:
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        return

    today = date.today()
    daily_log = await DailyLog.get_or_none(user=user, date=today)

    if not daily_log:
        await message.answer("Сегодня нечего завершать. Напиши /morning")
        return

    # Получаем все шаги
    steps = await Step.filter(id__in=daily_log.assigned_step_ids)
    completed = [s for s in steps if s.status == "completed"]

    await finish_day(message, user, steps, completed, daily_log, state)
