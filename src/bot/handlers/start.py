"""Базовые хендлеры: /start, /help, /id."""

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Приветствие и краткое описание возможностей."""
    await message.answer(
        "Привет! Я Antipanic Bot — помогаю ставить цели, планировать этапы "
        "и разруливать залипание.\n\n"
        "Начни с /help, чтобы увидеть доступные команды."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Краткая справка по командам."""
    await message.answer(
        "Доступные команды:\n"
        "/start — приветствие\n"
        "/help — эта подсказка\n"
        "/ping — проверить, что бот жив\n"
        "/id — показать твой Telegram ID\n"
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    """Вернуть Telegram ID пользователя (удобно для whitelist)."""
    user_id = message.from_user.id if message.from_user else "unknown"
    await message.answer(f"Твой Telegram ID: {user_id}")

