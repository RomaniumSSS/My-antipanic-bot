"""
Onboarding handlers — создание цели и этапов.

Flow (упрощённый для TMA миграции):
1. Пользователь вводит цель (из start.py → OnboardingStates.waiting_for_goal)
2. Пользователь вводит дедлайн
3. Создание Goal + 1 дефолтный Stage "Начало" в БД (без AI)

AICODE-NOTE: Упрощено для Этапа 1.2 TMA миграции.
AI генерация этапов перенесена в BACKLOG.md для будущей реализации.
"""

import logging
from datetime import date, timedelta

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import main_menu_keyboard
from src.bot.states import OnboardingStates
from src.database.models import Goal, Stage, User
from src.services.reminders import setup_user_reminders

logger = logging.getLogger(__name__)

router = Router()


def parse_date(text: str) -> date | None:
    """
    Парсинг даты из текста пользователя.
    Поддерживает форматы:
    - DD.MM.YYYY или DD/MM/YYYY
    - YYYY-MM-DD
    - "+N дней" или "через N дней"
    """
    text = text.strip().lower()

    # Относительные даты
    if text.startswith("+") or "через" in text or "дней" in text or "дня" in text:
        import re

        match = re.search(r"(\d+)", text)
        if match:
            days = int(match.group(1))
            return date.today() + timedelta(days=days)

    # DD.MM.YYYY или DD/MM/YYYY
    for sep in [".", "/"]:
        if sep in text:
            parts = text.split(sep)
            if len(parts) == 3:
                try:
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                    if year < 100:
                        year += 2000
                    return date(year, month, day)
                except (ValueError, IndexError):
                    pass

    # YYYY-MM-DD
    if "-" in text:
        try:
            parts = text.split("-")
            if len(parts) == 3 and len(parts[0]) == 4:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            pass

    return None


@router.message(OnboardingStates.waiting_for_goal)
async def process_goal(message: Message, state: FSMContext) -> None:
    """Получение цели от пользователя."""
    goal_text = message.text
    if not goal_text or len(goal_text) < 5:
        await message.answer("Опиши цель подробнее (хотя бы 5 символов).")
        return

    await state.update_data(goal_text=goal_text)
    await state.set_state(OnboardingStates.waiting_for_deadline)

    await message.answer(
        f"🎯 *{goal_text}*\n\n"
        "*Когда хочешь достичь?*\n"
        "Напиши: `25.12.2025` или `+30 дней`"
    )


@router.message(OnboardingStates.waiting_for_deadline)
async def process_deadline(message: Message, state: FSMContext) -> None:
    """
    Получение дедлайна и создание цели.

    AICODE-NOTE: Упрощено - теперь создаём Goal + 1 Stage "Начало" сразу,
    без AI генерации этапов и подтверждения.
    """
    deadline = parse_date(message.text or "")

    if not deadline:
        await message.answer("Не понял. Примеры: `25.12.2025` или `+30 дней`")
        return

    if deadline <= date.today():
        await message.answer("Дедлайн должен быть в будущем. Укажи другую дату.")
        return

    data = await state.get_data()
    goal_text = data["goal_text"]

    # Получаем пользователя
    if not message.from_user:
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Пользователь не найден. Напиши /start")
        return

    # AICODE-NOTE: Создаём цель без AI этапов
    goal = await Goal.create(
        user=user,
        title=goal_text,
        deadline=deadline,
        start_date=date.today(),
        status="active",
    )

    # AICODE-NOTE: Создаём 1 дефолтный этап "Начало" на весь срок
    await Stage.create(
        goal=goal,
        title="Начало",
        order=1,
        start_date=date.today(),
        end_date=deadline,
        status="active",
    )

    # Настраиваем напоминания
    await setup_user_reminders(user)

    await state.clear()

    await message.answer(
        f"✅ *Цель создана!*\n\n"
        f"🎯 {goal_text}\n"
        f"📅 До {deadline.strftime('%d.%m.%Y')}\n\n"
        "Жми *Утро* — спланируем первый день.",
        reply_markup=main_menu_keyboard(),
    )

    logger.info(f"Goal created for user {user.telegram_id}: {goal_text}")


# AICODE-NOTE: Удалены handler'ы для OnboardingStates.confirming_stages
# (confirm_stages, edit_stages, cancel_onboarding) после упрощения онбординга.
# Теперь цель создаётся сразу после ввода дедлайна без подтверждения.
