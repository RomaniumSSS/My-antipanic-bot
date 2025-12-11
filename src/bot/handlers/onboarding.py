"""
Onboarding handlers — создание цели и этапов.

Flow:
1. Пользователь вводит цель (из start.py → OnboardingStates.waiting_for_goal)
2. Пользователь вводит дедлайн
3. AI разбивает цель на этапы
4. Пользователь подтверждает или редактирует
5. Создание Goal + Stages в БД
"""

import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.callbacks.data import ConfirmAction, ConfirmCallback
from src.bot.keyboards import confirm_keyboard, main_menu_keyboard
from src.bot.states import OnboardingStates
from src.database.models import Goal, Stage, User
from src.services.ai import ai_service
from src.services.scheduler import setup_user_reminders

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
    """Получение дедлайна и генерация этапов."""
    deadline = parse_date(message.text or "")

    if not deadline:
        await message.answer("Не понял. Примеры: `25.12.2025` или `+30 дней`")
        return

    if deadline <= date.today():
        await message.answer("Дедлайн должен быть в будущем. Укажи другую дату.")
        return

    data = await state.get_data()
    goal_text = data["goal_text"]

    await state.update_data(deadline=deadline.isoformat())

    # Генерируем этапы через AI
    wait_msg = await message.answer("🤔 Разбиваю цель на этапы...")

    stages_data = await ai_service.decompose_goal(goal_text, deadline)

    await state.update_data(stages=stages_data)

    # Формируем текст этапов для показа
    total_days = (deadline - date.today()).days
    stages_text = ""
    current_day = 0
    for i, stage in enumerate(stages_data, 1):
        days = stage.get("days", total_days // len(stages_data))
        stages_text += f"{i}. *{stage['title']}* (~{days} дн.)\n"
        current_day += days

    await wait_msg.delete()
    await state.set_state(OnboardingStates.confirming_stages)

    await message.answer(
        f"🎯 *{goal_text}*\n"
        f"📅 Дедлайн: {deadline.strftime('%d.%m.%Y')}\n\n"
        f"*Этапы:*\n{stages_text}\n"
        "Всё верно?",
        reply_markup=confirm_keyboard(),
    )


@router.callback_query(
    OnboardingStates.confirming_stages,
    ConfirmCallback.filter(F.action == ConfirmAction.yes),
)
async def confirm_stages(callback: CallbackQuery, state: FSMContext) -> None:
    """Подтверждение этапов и создание цели."""
    await callback.answer()

    data = await state.get_data()
    goal_text = data["goal_text"]
    deadline = date.fromisoformat(data["deadline"])
    stages_data = data["stages"]

    # Получаем пользователя
    if not callback.from_user:
        return

    user = await User.get_or_none(telegram_id=callback.from_user.id)
    if not user:
        await state.clear()
        await callback.message.edit_text("Пользователь не найден. Напиши /start")
        return

    # Создаём цель
    goal = await Goal.create(
        user=user,
        title=goal_text,
        deadline=deadline,
        start_date=date.today(),
        status="active",
    )

    # Создаём этапы
    current_date = date.today()
    for i, stage_info in enumerate(stages_data):
        days = stage_info.get("days", 7)
        end_date = current_date + timedelta(days=days)

        await Stage.create(
            goal=goal,
            title=stage_info["title"],
            order=i + 1,
            start_date=current_date,
            end_date=end_date,
            status="active" if i == 0 else "pending",
        )
        current_date = end_date + timedelta(days=1)

    # Настраиваем напоминания
    await setup_user_reminders(
        user_id=user.telegram_id,
        morning_time=user.reminder_morning,
        evening_time=user.reminder_evening,
    )

    await state.clear()

    await callback.message.edit_text(
        f"✅ *Цель создана!*\n\n"
        f"🎯 {goal_text}\n"
        f"📅 До {deadline.strftime('%d.%m.%Y')}\n\n"
        "Жми *Утро* — спланируем первый день.",
        reply_markup=main_menu_keyboard(),
    )

    logger.info(f"Goal created for user {user.telegram_id}: {goal_text}")


@router.callback_query(
    OnboardingStates.confirming_stages,
    ConfirmCallback.filter(F.action == ConfirmAction.edit),
)
async def edit_stages(callback: CallbackQuery, state: FSMContext) -> None:
    """Редактирование этапов (упрощённый вариант — ввод заново)."""
    await callback.answer()

    await state.set_state(OnboardingStates.waiting_for_goal)

    await callback.message.edit_text(
        "Хорошо, давай начнём сначала.\n\n" "*Какую цель ты хочешь достичь?*"
    )


@router.callback_query(
    OnboardingStates.confirming_stages,
    ConfirmCallback.filter(F.action == ConfirmAction.cancel),
)
async def cancel_onboarding(callback: CallbackQuery, state: FSMContext) -> None:
    """Отмена создания цели."""
    await callback.answer()
    await state.clear()

    await callback.message.edit_text("Ок, отменил. Когда будешь готов — напиши /start")
