"""
Базовые хендлеры: /start, /help, /id, /status.
"""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from src.bot.keyboards import main_menu_keyboard
from src.bot.states import OnboardingStates
from src.bot.utils import escape_markdown
from src.config import config
from src.database.models import Goal, User


def tma_keyboard() -> InlineKeyboardMarkup | None:
    """Inline keyboard with TMA button (if TMA_URL configured)."""
    if not config.TMA_URL:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Открыть приложение",
                    web_app=WebAppInfo(url=config.TMA_URL),
                )
            ]
        ]
    )


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
    - С активной целью → статус + меню
    - Без цели → прямой переход в онбординг
    """
    user = await get_or_create_user(message)

    # Проверяем активную цель
    active_goal = (
        await Goal.filter(user=user, status="active").prefetch_related("stages").first()
    )

    if active_goal:
        # Есть активная цель — показываем статус
        stages = await active_goal.stages.all().order_by("order")
        current_stage = next((s for s in stages if s.status == "active"), None)

        if current_stage:
            stage_info = f"📍 _{escape_markdown(current_stage.title)}_"
        else:
            stage_info = "✅ Все этапы завершены!"

        await message.answer(
            f"🎯 *{escape_markdown(active_goal.title)}*\n"
            f"{stage_info}\n\n"
            f"Жми *Утро* — спланируем день.\n"
            f"Застрял? Жми *Застрял* — помогу.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Проверяем незавершенный onboarding goal (защита от цикла)
    onboarding_goal = await Goal.filter(user=user, status="onboarding").first()
    if onboarding_goal:
        # Стираем временный onboarding goal и сразу переводим в ввод цели
        await onboarding_goal.delete()
        await state.set_state(OnboardingStates.waiting_for_goal)
        await message.answer(
            "🔥 Давай закончим онбординг.\n\n"
            "*Какую цель хочешь достичь?*\n"
            "Например: выучить Python, запустить блог, похудеть на 5 кг"
        )
        return

    await state.clear()

    # AICODE-NOTE: Welcome message для новых пользователей (UX fix 17.12.2025)
    # Объясняем, что это за бот и как им пользоваться
    await message.answer(
        "👋 *Привет! Я Antipanic Bot*\n\n"
        "Помогаю преодолеть прокрастинацию и паралич действий.\n\n"
        "*Как это работает:*\n"
        "1️⃣ Ты ставишь цель\n"
        "2️⃣ Я разбиваю её на микро-шаги (2-5 минут)\n"
        "3️⃣ Каждое утро — новый план дня\n"
        "4️⃣ Застрял? Жми *Застрял* — помогу сдвинуться\n\n"
        "🎯 *Главные команды:*\n"
        "• *Утро* — план на день\n"
        "• *Застрял* — быстрая помощь\n"
        "• *Вечер* — подведение итогов\n\n"
        "Поехали! 🔥",
        reply_markup=main_menu_keyboard(),
    )

    await state.set_state(OnboardingStates.waiting_for_goal)
    await message.answer(
        "*Какую цель хочешь достичь?*\n\n"
        "Например:\n"
        "• Выучить Python\n"
        "• Запустить блог\n"
        "• Похудеть на 5 кг"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Краткая справка по командам."""
    await message.answer(
        "*Команды:*\n\n"
        "/morning — план на день\n"
        "/stuck — помощь при ступоре\n"
        "/status — прогресс\n"
        "/evening — итоги дня\n"
        "/app — открыть приложение\n"
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
    active_goal = (
        await Goal.filter(user=user, status="active").prefetch_related("stages").first()
    )

    if not active_goal:
        await message.answer(
            "У тебя пока нет активной цели.\nНапиши /start чтобы создать.",
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
        stages_text += f"{icon} {i}. {escape_markdown(stage.title)} ({stage.progress}%)\n"

    days_left = (active_goal.deadline - active_goal.start_date).days

    await message.answer(
        f"🎯 *{escape_markdown(active_goal.title)}*\n\n"
        f"*Этапы:*\n{stages_text}\n"
        f"📅 Осталось дней: {days_left}\n"
        f"🔥 Streak: {user.streak_days} дней\n"
        f"⭐ XP: {user.xp}",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text.casefold().in_(("📱 приложение", "приложение", "/app")))
async def app_from_menu(message: Message) -> None:
    """Поддержка кнопки меню для открытия приложения."""
    await cmd_app(message)


@router.message(Command("app"))
async def cmd_app(message: Message) -> None:
    """Открыть Telegram Mini App."""
    keyboard = tma_keyboard()
    if keyboard:
        await message.answer(
            "📱 *Antipanic App*\n\nСтатистика, цели и прогресс в одном месте.",
            reply_markup=keyboard,
        )
    else:
        await message.answer(
            "⚠️ Mini App пока не настроен.\nИспользуй /status для просмотра прогресса."
        )
