"""
Evening handlers — вечерний итог дня.

Flow:
1. /evening → показ шагов с отметками
2. Предложение отметить неотмеченные
3. Оценка дня (1-5)
4. Обновление streak, XP
"""

import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.callbacks.data import RatingCallback
from src.bot.keyboards import main_menu_keyboard, rating_keyboard, steps_list_keyboard
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

    # Если есть неотмеченные — предлагаем отметить
    if pending:
        await message.answer(
            f"🌙 *Вечерний итог*\n\n"
            f"*Шаги дня:*\n{steps_text}\n"
            f"Есть неотмеченные шаги. Отметь их или оставь как есть:",
            reply_markup=steps_list_keyboard([s.id for s in pending]),
        )
        await state.set_state(EveningStates.marking_done)
        await state.update_data(pending_count=len(pending))
    else:
        # Все отмечены — сразу к оценке
        await show_rating_prompt(message, steps, completed, daily_log, state)


async def show_rating_prompt(
    message: Message,
    steps: list,
    completed: list,
    daily_log: DailyLog,
    state: FSMContext,
) -> None:
    """Показать запрос оценки дня."""
    total = len(steps)
    done = len(completed)
    xp_earned = daily_log.xp_earned or 0

    await state.set_state(EveningStates.rating_day)

    steps_text = ""
    for s in steps:
        if s.status == "completed":
            icon = "✅"
        elif s.status == "skipped":
            icon = "⏭"
        else:
            icon = "⬜"
        steps_text += f"{icon} {s.title}\n"

    await message.answer(
        f"🌙 *Итоги дня*\n\n"
        f"{steps_text}\n"
        f"📊 Выполнено: {done}/{total}\n"
        f"⭐ XP за день: +{xp_earned}\n\n"
        "Как прошёл день?",
        reply_markup=rating_keyboard(),
    )


@router.callback_query(EveningStates.rating_day, RatingCallback.filter())
async def process_rating(
    callback: CallbackQuery, callback_data: RatingCallback, state: FSMContext
) -> None:
    """Обработка оценки дня."""
    await callback.answer()

    rating = callback_data.value

    if not callback.from_user:
        return

    user = await User.get_or_none(telegram_id=callback.from_user.id)
    if not user:
        await state.clear()
        await callback.message.edit_text("Пользователь не найден.")
        return

    today = date.today()
    daily_log = await DailyLog.get_or_none(user=user, date=today)

    if daily_log:
        daily_log.day_rating = str(rating)
        await daily_log.save()

    # Обновляем streak
    update_streak(user, today)
    await user.save()

    await state.clear()

    # Формируем итоговое сообщение
    rating_emoji = ["😫", "😕", "😐", "🙂", "😊"][rating - 1]

    streak_text = ""
    if user.streak_days >= 3:
        streak_text = f"\n🔥 *Streak: {user.streak_days} дней подряд!*"
    elif user.streak_days > 0:
        streak_text = f"\n🔥 Streak: {user.streak_days}"

    # Мотивационное сообщение в зависимости от оценки
    if rating >= 4:
        motivation = "Отличный день! Так держать 💪"
    elif rating == 3:
        motivation = "Нормальный день. Завтра будет лучше!"
    else:
        motivation = "Бывает. Главное — не сдаваться 🤗"

    await callback.message.edit_text(
        f"🌙 *День завершён!*\n\n"
        f"Оценка: {rating_emoji}\n"
        f"⭐ Всего XP: {user.xp}{streak_text}\n\n"
        f"{motivation}\n\n"
        "До завтра! Напишу утром 🌅"
    )

    logger.info(
        f"Evening completed for user {user.telegram_id}: "
        f"rating={rating}, streak={user.streak_days}"
    )


@router.message(Command("finish_day"))
async def cmd_finish_day(message: Message, state: FSMContext) -> None:
    """Альтернативная команда для завершения дня (пропуск неотмеченных)."""
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

    await show_rating_prompt(message, steps, completed, daily_log, state)
