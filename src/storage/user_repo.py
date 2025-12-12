"""
User Repository - тупые CRUD операции для User модели.

AICODE-NOTE: Репозиторий содержит только доступ к данным, БЕЗ бизнес-логики.
Бизнес-логика (расчет streak, level) находится в core/domain/gamification.py.
"""

from typing import Optional

from src.database.models import User


async def get_user(telegram_id: int) -> Optional[User]:
    """Получить пользователя по telegram_id."""
    return await User.get_or_none(telegram_id=telegram_id)


async def update_xp(user: User, xp_delta: int) -> User:
    """Добавить XP пользователю."""
    user.xp += xp_delta
    await user.save()
    return user


async def update_streak(user: User, new_streak: int) -> User:
    """Обновить streak пользователя."""
    user.streak_days = new_streak
    await user.save()
    return user


async def save_user(user: User) -> User:
    """Сохранить изменения пользователя."""
    await user.save()
    return user
