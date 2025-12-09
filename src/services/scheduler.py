"""
Scheduler Service — планировщик напоминаний.

Использует APScheduler 4.x (AsyncScheduler).
Напоминания: утреннее (/morning) и вечернее (/evening).

AICODE-NOTE: Используем in-memory scheduler для MVP.
Для production с персистентностью — добавить SQLAlchemyDataStore.
"""

import logging
from typing import Optional

from aiogram import Bot
from apscheduler import AsyncScheduler, ConflictPolicy
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Глобальный scheduler instance
scheduler = AsyncScheduler()

# Ссылка на Bot для отправки сообщений из задач
_bot: Optional[Bot] = None


def set_bot(bot: Bot) -> None:
    """Установить инстанс бота для использования в задачах."""
    global _bot
    _bot = bot


def get_bot() -> Bot:
    """Получить инстанс бота."""
    if _bot is None:
        raise RuntimeError("Bot not initialized in scheduler. Call set_bot() first.")
    return _bot


# === Задачи напоминаний ===


async def send_morning_reminder(user_id: int) -> None:
    """Утреннее напоминание — предлагает начать /morning."""
    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "🌅 *Доброе утро!*\n\n"
                "Как твоя энергия сегодня? Давай спланируем день.\n\n"
                "Напиши /morning"
            ),
            parse_mode="Markdown",
        )
        logger.info(f"Morning reminder sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send morning reminder to {user_id}: {e}")


async def send_evening_reminder(user_id: int) -> None:
    """Вечернее напоминание — предлагает подвести итоги."""
    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "🌙 *Вечер!*\n\n"
                "Как прошёл день? Давай подведём итоги.\n\n"
                "Напиши /evening"
            ),
            parse_mode="Markdown",
        )
        logger.info(f"Evening reminder sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send evening reminder to {user_id}: {e}")


async def send_nudge_reminder(user_id: int) -> None:
    """Дневной пинг — если шаги не отмечены."""
    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "👋 Привет! Как дела с шагами?\n\n"
                "Если застрял — напиши /stuck, помогу разобраться."
            ),
            parse_mode="Markdown",
        )
        logger.info(f"Nudge reminder sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send nudge reminder to {user_id}: {e}")


# === API для управления напоминаниями пользователя ===


async def setup_user_reminders(
    user_id: int, morning_time: str = "09:00", evening_time: str = "21:00"
) -> None:
    """
    Настроить напоминания для пользователя.

    Args:
        user_id: Telegram ID пользователя
        morning_time: Время утреннего напоминания (HH:MM)
        evening_time: Время вечернего напоминания (HH:MM)
    """
    morning_h, morning_m = map(int, morning_time.split(":"))
    evening_h, evening_m = map(int, evening_time.split(":"))

    # Утреннее напоминание
    await scheduler.add_schedule(
        send_morning_reminder,
        trigger=CronTrigger(hour=morning_h, minute=morning_m),
        id=f"morning_{user_id}",
        args=[user_id],
        conflict_policy=ConflictPolicy.replace,
    )

    # Вечернее напоминание
    await scheduler.add_schedule(
        send_evening_reminder,
        trigger=CronTrigger(hour=evening_h, minute=evening_m),
        id=f"evening_{user_id}",
        args=[user_id],
        conflict_policy=ConflictPolicy.replace,
    )

    logger.info(
        f"Reminders set for user {user_id}: "
        f"morning={morning_time}, evening={evening_time}"
    )


async def update_user_reminders(
    user_id: int,
    morning_time: Optional[str] = None,
    evening_time: Optional[str] = None,
) -> None:
    """Обновить время напоминаний (только указанные)."""
    if morning_time:
        morning_h, morning_m = map(int, morning_time.split(":"))
        await scheduler.add_schedule(
            send_morning_reminder,
            trigger=CronTrigger(hour=morning_h, minute=morning_m),
            id=f"morning_{user_id}",
            args=[user_id],
            conflict_policy=ConflictPolicy.replace,
        )
        logger.info(f"Morning reminder updated for {user_id}: {morning_time}")

    if evening_time:
        evening_h, evening_m = map(int, evening_time.split(":"))
        await scheduler.add_schedule(
            send_evening_reminder,
            trigger=CronTrigger(hour=evening_h, minute=evening_m),
            id=f"evening_{user_id}",
            args=[user_id],
            conflict_policy=ConflictPolicy.replace,
        )
        logger.info(f"Evening reminder updated for {user_id}: {evening_time}")


async def pause_user_reminders(user_id: int) -> None:
    """Приостановить все напоминания пользователя."""
    try:
        await scheduler.pause_schedule(f"morning_{user_id}")
        await scheduler.pause_schedule(f"evening_{user_id}")
        logger.info(f"Reminders paused for user {user_id}")
    except Exception as e:
        logger.warning(f"Could not pause reminders for {user_id}: {e}")


async def resume_user_reminders(user_id: int) -> None:
    """Возобновить напоминания пользователя."""
    try:
        await scheduler.unpause_schedule(f"morning_{user_id}")
        await scheduler.unpause_schedule(f"evening_{user_id}")
        logger.info(f"Reminders resumed for user {user_id}")
    except Exception as e:
        logger.warning(f"Could not resume reminders for {user_id}: {e}")


async def remove_user_reminders(user_id: int) -> None:
    """Полностью удалить напоминания пользователя."""
    try:
        await scheduler.remove_schedule(f"morning_{user_id}")
    except Exception:
        pass  # Может не существовать
    try:
        await scheduler.remove_schedule(f"evening_{user_id}")
    except Exception:
        pass
    logger.info(f"Reminders removed for user {user_id}")


# === Lifecycle ===

_scheduler_task = None


async def start() -> None:
    """Запустить планировщик (вызывать в on_startup)."""
    global _scheduler_task
    # APScheduler 4.x требует __aenter__ перед использованием
    await scheduler.__aenter__()
    _scheduler_task = True
    logger.info("Scheduler started")


async def stop() -> None:
    """Остановить планировщик (вызывать в on_shutdown)."""
    global _scheduler_task
    if _scheduler_task:
        await scheduler.__aexit__(None, None, None)
        _scheduler_task = None
    logger.info("Scheduler stopped")
