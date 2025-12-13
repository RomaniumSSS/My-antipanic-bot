"""
Reminder Service — напоминания через cron tick.

Простая архитектура:
1. Храним next_morning_reminder_at и next_evening_reminder_at в User (UTC)
2. /cron/tick вызывается каждые N минут (например, каждые 5 минут)
3. Выбираем всех пользователей где next_*_reminder_at <= now
4. Отправляем напоминание
5. Пересчитываем next_*_reminder_at на следующий день

Без APScheduler, без greenlet, без libstdc++.so.6 — чистая математика дат.
"""

import logging
from datetime import datetime, time, timedelta

from aiogram import Bot

from src.database.models import User

logger = logging.getLogger(__name__)

# Глобальный Bot для отправки сообщений
_bot: Bot | None = None


def set_bot(bot: Bot) -> None:
    """Установить инстанс бота для использования в напоминаниях."""
    global _bot
    _bot = bot


def get_bot() -> Bot:
    """Получить инстанс бота."""
    if _bot is None:
        raise RuntimeError("Bot not initialized in reminders. Call set_bot() first.")
    return _bot


def calculate_next_reminder_time(
    reminder_time: str, timezone_offset: int, from_datetime: datetime | None = None
) -> datetime:
    """
    Вычислить следующее время напоминания в UTC.

    Args:
        reminder_time: Время в формате HH:MM (в часовом поясе пользователя)
        timezone_offset: Смещение часового пояса от UTC (например, +3 для МСК)
        from_datetime: От какого времени считать (по умолчанию — сейчас UTC)

    Returns:
        datetime в UTC когда нужно отправить напоминание
    """
    if from_datetime is None:
        from_datetime = datetime.utcnow()

    # Парсим время
    hour, minute = map(int, reminder_time.split(":"))
    local_time = time(hour, minute)

    # Получаем сегодняшнюю дату в часовом поясе пользователя
    # from_datetime - это UTC, прибавляем offset чтобы получить local
    user_local_now = from_datetime + timedelta(hours=timezone_offset)
    user_local_date = user_local_now.date()

    # Создаём datetime в локальном времени пользователя
    local_reminder_dt = datetime.combine(user_local_date, local_time)

    # Если это время уже прошло сегодня — берём завтра
    if local_reminder_dt <= user_local_now:
        local_reminder_dt += timedelta(days=1)

    # Конвертируем обратно в UTC
    utc_reminder_dt = local_reminder_dt - timedelta(hours=timezone_offset)

    return utc_reminder_dt


async def setup_user_reminders(user: User) -> None:
    """
    Настроить напоминания для пользователя.
    Вычисляет next_morning_reminder_at и next_evening_reminder_at.
    """
    if not user.reminders_enabled:
        logger.info(f"Reminders disabled for user {user.telegram_id}")
        return

    now_utc = datetime.utcnow()

    # Вычисляем следующее утреннее напоминание
    user.next_morning_reminder_at = calculate_next_reminder_time(
        user.reminder_morning, user.timezone_offset, now_utc
    )

    # Вычисляем следующее вечернее напоминание
    user.next_evening_reminder_at = calculate_next_reminder_time(
        user.reminder_evening, user.timezone_offset, now_utc
    )

    await user.save()

    logger.info(
        f"Reminders set for user {user.telegram_id}: "
        f"morning={user.next_morning_reminder_at}, evening={user.next_evening_reminder_at}"
    )


async def send_morning_reminder(user: User) -> None:
    """Отправить утреннее напоминание пользователю."""
    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=(
                "🌅 *Доброе утро!*\n\n"
                "Как твоя энергия сегодня? Давай спланируем день.\n\n"
                "Напиши /morning"
            ),
            parse_mode="Markdown",
        )
        logger.info(f"Morning reminder sent to user {user.telegram_id}")

        # Пересчитываем следующее утреннее напоминание (завтра)
        user.next_morning_reminder_at = calculate_next_reminder_time(
            user.reminder_morning, user.timezone_offset
        )
        await user.save()

    except Exception as e:
        logger.error(f"Failed to send morning reminder to {user.telegram_id}: {e}")


async def send_evening_reminder(user: User) -> None:
    """Отправить вечернее напоминание пользователю."""
    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=user.telegram_id,
            text=(
                "🌙 *Вечер!*\n\n"
                "Как прошёл день? Давай подведём итоги.\n\n"
                "Напиши /evening"
            ),
            parse_mode="Markdown",
        )
        logger.info(f"Evening reminder sent to user {user.telegram_id}")

        # Пересчитываем следующее вечернее напоминание (завтра)
        user.next_evening_reminder_at = calculate_next_reminder_time(
            user.reminder_evening, user.timezone_offset
        )
        await user.save()

    except Exception as e:
        logger.error(f"Failed to send evening reminder to {user.telegram_id}: {e}")


async def process_reminders() -> dict[str, int]:
    """
    Обработать все напоминания (вызывается из /cron/tick).

    Returns:
        Статистика: {"morning_sent": N, "evening_sent": N}
    """
    now_utc = datetime.utcnow()
    stats = {"morning_sent": 0, "evening_sent": 0}

    # Найти пользователей с просроченными утренними напоминаниями
    morning_users = await User.filter(
        reminders_enabled=True,
        next_morning_reminder_at__lte=now_utc,
    ).all()

    for user in morning_users:
        await send_morning_reminder(user)
        stats["morning_sent"] += 1

    # Найти пользователей с просроченными вечерними напоминаниями
    evening_users = await User.filter(
        reminders_enabled=True,
        next_evening_reminder_at__lte=now_utc,
    ).all()

    for user in evening_users:
        await send_evening_reminder(user)
        stats["evening_sent"] += 1

    logger.info(
        f"Reminders processed: {stats['morning_sent']} morning, {stats['evening_sent']} evening"
    )

    return stats
