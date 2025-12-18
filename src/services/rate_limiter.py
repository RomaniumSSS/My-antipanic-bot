"""
Rate Limiter для AI вызовов - Plan 005.

Лимиты:
- Morning flow: 5 вызовов в день
- Stuck flow: 10 вызовов в день

AICODE-NOTE: Защита от спама AI запросов и переплаты за API.
"""

import logging
from dataclasses import dataclass
from datetime import date

from src.database.models import User
from src.storage import daily_log_repo

logger = logging.getLogger(__name__)

# Лимиты AI вызовов в день
MAX_MORNING_CALLS = 5
MAX_STUCK_CALLS = 10


@dataclass
class RateLimitResult:
    """Результат проверки лимита."""

    allowed: bool
    current_count: int
    max_count: int
    message: str = ""


class RateLimiter:
    """Сервис для проверки и отслеживания AI лимитов."""

    async def check_morning_limit(self, user: User) -> RateLimitResult:
        """
        Проверить лимит morning вызовов.

        Args:
            user: User instance

        Returns:
            RateLimitResult с информацией о лимите
        """
        daily_log = await daily_log_repo.get_or_create_daily_log(user, date.today())
        current = daily_log.morning_calls_count

        if current >= MAX_MORNING_CALLS:
            return RateLimitResult(
                allowed=False,
                current_count=current,
                max_count=MAX_MORNING_CALLS,
                message=(
                    f"⏳ Достиг лимита morning на сегодня ({current}/{MAX_MORNING_CALLS}).\n\n"
                    "Попробуй завтра утром 🌅"
                ),
            )

        return RateLimitResult(
            allowed=True,
            current_count=current,
            max_count=MAX_MORNING_CALLS,
        )

    async def check_stuck_limit(self, user: User) -> RateLimitResult:
        """
        Проверить лимит stuck вызовов.

        Args:
            user: User instance

        Returns:
            RateLimitResult с информацией о лимите
        """
        daily_log = await daily_log_repo.get_or_create_daily_log(user, date.today())
        current = daily_log.stuck_calls_count

        if current >= MAX_STUCK_CALLS:
            return RateLimitResult(
                allowed=False,
                current_count=current,
                max_count=MAX_STUCK_CALLS,
                message=(
                    f"⏳ Достиг лимита stuck помощи на сегодня ({current}/{MAX_STUCK_CALLS}).\n\n"
                    "Попробуй завтра 🌅"
                ),
            )

        return RateLimitResult(
            allowed=True,
            current_count=current,
            max_count=MAX_STUCK_CALLS,
        )

    async def increment_morning_calls(self, user: User) -> None:
        """
        Увеличить счётчик morning вызовов.

        Args:
            user: User instance
        """
        daily_log = await daily_log_repo.get_or_create_daily_log(user, date.today())
        daily_log.morning_calls_count += 1
        await daily_log.save()

        logger.info(
            f"Morning call incremented for user {user.telegram_id}: "
            f"{daily_log.morning_calls_count}/{MAX_MORNING_CALLS}"
        )

    async def increment_stuck_calls(self, user: User) -> None:
        """
        Увеличить счётчик stuck вызовов.

        Args:
            user: User instance
        """
        daily_log = await daily_log_repo.get_or_create_daily_log(user, date.today())
        daily_log.stuck_calls_count += 1
        await daily_log.save()

        logger.info(
            f"Stuck call incremented for user {user.telegram_id}: "
            f"{daily_log.stuck_calls_count}/{MAX_STUCK_CALLS}"
        )

    async def get_usage_stats(self, user: User) -> dict[str, int]:
        """
        Получить статистику использования AI за день.

        Args:
            user: User instance

        Returns:
            Dict с текущим использованием и лимитами
        """
        daily_log = await daily_log_repo.get_or_create_daily_log(user, date.today())

        return {
            "morning_used": daily_log.morning_calls_count,
            "morning_max": MAX_MORNING_CALLS,
            "stuck_used": daily_log.stuck_calls_count,
            "stuck_max": MAX_STUCK_CALLS,
        }


# Singleton instance
rate_limiter = RateLimiter()
