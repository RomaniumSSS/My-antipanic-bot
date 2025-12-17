"""
Evening handlers — вечерний итог дня.

Flow (упрощённый для TMA миграции):
1. /evening → показ шагов с отметками
2. Предложение отметить неотмеченные
3. Обновление streak, XP → завершение

Handler is now thin - uses CompleteDailyReflectionUseCase for business logic.
"""

import logging
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import main_menu_keyboard, steps_list_keyboard
from src.bot.states import EveningStates
from src.core.use_cases.complete_daily_reflection import (
    complete_daily_reflection_use_case,
)
from src.database.models import User

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text.casefold().in_(("вечер", "/evening")))
async def evening_from_menu(message: Message, state: FSMContext) -> None:
    """Поддержка кнопки меню для запуска /evening."""
    await cmd_evening(message, state)


@router.message(Command("evening"))
async def cmd_evening(message: Message, state: FSMContext) -> None:
    """
    Начало вечернего итога.

    Uses CompleteDailyReflectionUseCase.get_daily_summary() to get steps and stats.
    """
    if not message.from_user:
        logger.warning("evening: message.from_user is None")
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        await state.clear()
        await message.answer(
            "Сначала напиши /start",
            reply_markup=main_menu_keyboard(),
        )
        return

    today = date.today()

    try:
        # AICODE-NOTE: Debug logging for evening crash investigation (17.12.2025)
        logger.info(f"Evening flow started for user {user.telegram_id}, today={today}")

        # Use use-case to get daily summary
        summary = await complete_daily_reflection_use_case.get_daily_summary(user, today)

        logger.info(f"Evening summary result: success={summary.success}, steps_count={len(summary.steps or [])}")

        if not summary.success:
            await state.clear()
            await message.answer(
                summary.error_message,
                reply_markup=main_menu_keyboard(),
            )
            return

        # Show summary with pending steps keyboard if any
        if summary.has_pending and summary.pending_step_ids:
            await message.answer(
                f"🌙 *Вечерний итог*\n\n"
                f"*Шаги дня:*\n{summary.steps_text}\n\n"
                f"Есть неотмеченные шаги. Отметь их или нажми кнопку ниже для завершения:",
                reply_markup=steps_list_keyboard(summary.pending_step_ids),
                parse_mode="Markdown",
            )
            await state.set_state(EveningStates.marking_done)
        else:
            # All steps marked → complete day
            await finish_day(message, user, state)
    except Exception as e:
        logger.exception(f"Error in cmd_evening for user {user.telegram_id}: {e}")
        await state.clear()
        await message.answer(
            "❌ Не удалось загрузить итоги дня. Попробуй позже или напиши /start",
            reply_markup=main_menu_keyboard(),
        )


async def finish_day(message: Message, user: User, state: FSMContext) -> None:
    """
    Завершение дня (упрощённое).

    Uses CompleteDailyReflectionUseCase.complete_day() to update streak and get stats.

    AICODE-NOTE: Handler теперь тонкий - только вызов use-case и отображение результата.
    """
    today = date.today()

    try:
        # AICODE-NOTE: Debug logging for finish_day (17.12.2025)
        logger.info(f"Finishing day for user {user.telegram_id}, today={today}")

        # Use use-case to complete day
        result = await complete_daily_reflection_use_case.complete_day(user, today)

        logger.info(f"Day completion result: success={result.success}")

        if not result.success:
            await state.clear()
            await message.answer(
                f"Не получилось завершить день: {result.error_message}",
                reply_markup=main_menu_keyboard(),
            )
            return

        await state.clear()

        # Show completion message with stats
        # AICODE-NOTE: Позитивный feedback после дня (CLAUDE_RULES.md § 2)
        await message.answer(
            f"🌙 *День завершён!*\n\n"
            f"{result.steps_text}\n\n"
            f"📊 Выполнено: {result.completed_steps}/{result.total_steps}\n"
            f"⭐ +{result.xp_earned} XP за день. Идёшь к цели.\n"
            f"⭐ Всего XP: {result.total_xp}{result.streak_text}\n\n"
            "До завтра! Напишу утром 🌅",
            reply_markup=main_menu_keyboard(),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception(f"Error in finish_day for user {user.telegram_id}: {e}")
        await state.clear()
        await message.answer(
            "❌ Не удалось завершить день. Попробуй позже или напиши /start",
            reply_markup=main_menu_keyboard(),
        )


@router.message(Command("finish_day"))
async def cmd_finish_day(message: Message, state: FSMContext) -> None:
    """
    Альтернативная команда для завершения дня (пропуск неотмеченных).

    AICODE-NOTE: Использует тот же use-case для завершения дня.
    """
    if not message.from_user:
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        return

    today = date.today()

    # Check if there's a daily log
    summary = await complete_daily_reflection_use_case.get_daily_summary(user, today)

    if not summary.success:
        await message.answer("Сегодня нечего завершать. Напиши /morning")
        return

    # Complete day using use-case
    await finish_day(message, user, state)
