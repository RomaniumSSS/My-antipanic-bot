"""Базовые хендлеры: /start, /help, /id, /status."""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.handlers.quiz import start_quiz
from src.bot.keyboards import main_menu_keyboard
from src.database.models import Goal, User

router = Router()


@router.message(F.text.casefold().in_(("статус", "/status")))
async def status_from_menu(message: Message) -> None:
    """Поддержка кнопки меню для /status."""
    await cmd_status(message)


async def get_or_create_user(message: Message) -> User:
    """Получить или создать пользователя по telegram_id."""
    if not message.from_user:
        raise ValueError("No user in message")

    user, _ = await User.get_or_create(
        telegram_id=message.from_user.id,
        defaults={
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
        },
    )
    return user


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    Точка входа:
    - Новый пользователь/без цели → квиз → мини-спринт → онбординг
    - С активной целью → статус + меню
    """
    user = await get_or_create_user(message)

    # Проверяем активную цель
    active_goal = await Goal.filter(user=user, status="active").first()

    if active_goal:
        # Есть активная цель — показываем статус
        stages = await active_goal.stages.all().order_by("order")
        current_stage = next((s for s in stages if s.status == "active"), None)

        if current_stage:
            stage_info = f"📍 _{current_stage.title}_"
        else:
            stage_info = "✅ Все этапы завершены!"

        await message.answer(
            f"🎯 *{active_goal.title}*\n"
            f"{stage_info}\n\n"
            f"Жми *Утро* — спланируем день.\n"
            f"Застрял? Жми *Застрял* — помогу.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Нет активной цели — запускаем квиз
    await start_quiz(message, state, user)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Краткая справка по командам."""
    await message.answer(
        "*Команды:*\n\n"
        "/morning — план на день\n"
        "/stuck — помощь при ступоре\n"
        "/status — прогресс\n"
        "/evening — итоги дня\n"
        "/start — новая цель"
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    """Вернуть Telegram ID пользователя (удобно для whitelist)."""
    user_id = message.from_user.id if message.from_user else "unknown"
    await message.answer(f"Твой Telegram ID: `{user_id}`")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    """Показать текущий прогресс по цели."""
    user = await get_or_create_user(message)
    active_goal = await Goal.filter(user=user, status="active").first()

    if not active_goal:
        await message.answer(
            "У тебя пока нет активной цели.\n" "Напиши /start чтобы создать.",
            reply_markup=main_menu_keyboard(),
        )
        return

    stages = await active_goal.stages.all().order_by("order")

    # Формируем список этапов с прогрессом
    stages_text = ""
    for i, stage in enumerate(stages, 1):
        if stage.status == "completed":
            icon = "✅"
        elif stage.status == "active":
            icon = "🔵"
        else:
            icon = "⚪"
        stages_text += f"{icon} {i}. {stage.title} ({stage.progress}%)\n"

    days_left = (active_goal.deadline - active_goal.start_date).days

    await message.answer(
        f"🎯 *{active_goal.title}*\n\n"
        f"*Этапы:*\n{stages_text}\n"
        f"📅 Осталось дней: {days_left}\n"
        f"🔥 Streak: {user.streak_days} дней\n"
        f"⭐ XP: {user.xp}",
        reply_markup=main_menu_keyboard(),
    )
