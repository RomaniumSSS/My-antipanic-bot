"""
Gamification Domain Rules - чистые функции для расчета XP, level, streak.

AICODE-NOTE: Чистые функции БЕЗ доступа к БД, БЕЗ side-effects.
Вызываются из use-cases для расчета наград.
"""

from datetime import date
from typing import Tuple

from src.database.models import Step, User


def calculate_xp_reward(step: Step) -> int:
    """
    Рассчитать награду XP за выполнение шага.

    Сейчас возвращает step.xp_reward из модели.
    В будущем можно добавить бонусы (streak, first completion, etc).
    """
    return step.xp_reward


def calculate_level(total_xp: int) -> int:
    """
    Рассчитать уровень пользователя на основе общего XP.

    Формула: level = sqrt(xp / 100)
    Например:
    - 0-99 XP = Level 0
    - 100-399 XP = Level 1
    - 400-899 XP = Level 2
    """
    import math

    return int(math.sqrt(total_xp / 100))


def calculate_streak(user: User, today: date) -> Tuple[int, bool]:
    """
    Рассчитать текущий streak пользователя.

    Возвращает:
    - новый streak (int)
    - флаг, увеличился ли streak (bool)

    Логика:
    - Если сегодня уже зачтено (streak_last_date == today) → streak не меняется
    - Если вчера была активность → streak += 1
    - Если пропущен день → streak = 1
    """
    last_activity = user.streak_last_date

    if last_activity == today:
        # Сегодня уже была активность, streak не меняется
        return user.streak_days, False

    if last_activity and (today - last_activity).days == 1:
        # Вчера была активность, увеличиваем streak
        return user.streak_days + 1, True

    # Пропущен день или первая активность
    return 1, True
