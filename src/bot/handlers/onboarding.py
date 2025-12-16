"""
Onboarding handlers — создание цели и этапов.

Flow:
1. Пользователь вводит цель (из start.py → OnboardingStates.waiting_for_goal)
2. Пользователь вводит дедлайн
3. AI генерирует 2-4 этапа цели
4. Создание Goal + Stages в БД

AICODE-NOTE: AI генерация этапов ВОЗВРАЩЕНА (была отключена для TMA миграции).
При ошибке AI — fallback на 1 дефолтный этап "Начало".
"""

import logging
from datetime import date, timedelta

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import main_menu_keyboard
from src.bot.states import OnboardingStates
from src.database.models import Goal, Stage, User
from src.services.ai import ai_service
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
    Получение дедлайна и создание цели с AI генерацией этапов.

    AICODE-NOTE: AI генерация ВОЗВРАЩЕНА. При ошибке AI — fallback на 1 этап.
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

    # Показываем сообщение о генерации
    wait_msg = await message.answer("⏳ Разбиваю цель на этапы...")

    # Генерируем этапы через AI
    try:
        stages_data = await ai_service.decompose_goal(goal_text, deadline)
    except Exception as e:
        logger.error(f"AI decompose_goal failed: {e}")
        stages_data = []

    # Fallback: если AI не вернул этапы — создаём 1 дефолтный
    if not stages_data:
        stages_data = [
            {"title": "Начало", "days": (deadline - date.today()).days}
        ]

    # Создаём цель
    goal = await Goal.create(
        user=user,
        title=goal_text,
        deadline=deadline,
        start_date=date.today(),
        status="active",
    )

    # Создаём этапы
    total_days = (deadline - date.today()).days
    current_start = date.today()
    stages_text = ""

    for i, stage_data in enumerate(stages_data, 1):
        stage_title = stage_data.get("title", f"Этап {i}")
        stage_days = stage_data.get("days", total_days // len(stages_data))

        # Рассчитываем даты этапа
        stage_end = current_start + timedelta(days=stage_days)
        if stage_end > deadline:
            stage_end = deadline

        # Первый этап active, остальные pending
        stage_status = "active" if i == 1 else "pending"

        await Stage.create(
            goal=goal,
            title=stage_title,
            order=i,
            start_date=current_start,
            end_date=stage_end,
            status=stage_status,
            progress=0,
        )

        # Формируем текст для показа
        icon = "🔵" if i == 1 else "⚪"
        stages_text += f"{icon} {i}. {stage_title}\n"

        current_start = stage_end + timedelta(days=1)

    # Настраиваем напоминания
    await setup_user_reminders(user)

    await state.clear()

    # Удаляем сообщение "Разбиваю..."
    try:
        await wait_msg.delete()
    except Exception:
        pass

    await message.answer(
        f"✅ *Цель создана!*\n\n"
        f"🎯 {goal_text}\n"
        f"📅 До {deadline.strftime('%d.%m.%Y')}\n\n"
        f"*Этапы:*\n{stages_text}\n"
        "Редактировать этапы: /goals\n"
        "Жми *Утро* — спланируем первый день.",
        reply_markup=main_menu_keyboard(),
    )

    logger.info(
        f"Goal created for user {user.telegram_id}: {goal_text} "
        f"with {len(stages_data)} stages"
    )


# AICODE-NOTE: AI генерация этапов ВОЗВРАЩЕНА.
# Handler'ы confirm_stages и edit_stages убраны — редактирование через /goals.
