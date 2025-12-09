"""Healthcheck и вспомогательные команды."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    """Проверка доступности бота."""
    await message.answer("pong")
