"""
Reflection Domain Rules - чистые функции для вечернего итога дня.

AICODE-NOTE: Чистые функции БЕЗ доступа к БД, БЕЗ side-effects.
Вызываются из use-cases для расчета статистики дня и форматирования итогов.

Extracted from handlers/evening.py for TMA migration Stage 2.4.
"""

from src.database.models import DailyLog, Step


def calculate_daily_progress(
    daily_log: DailyLog | None, steps: list[Step]
) -> dict[str, int]:
    """
    Рассчитать статистику дня.

    Args:
        daily_log: DailyLog за сегодня (может быть None)
        steps: Список шагов дня

    Returns:
        dict с ключами:
        - total: всего шагов
        - completed: выполнено
        - skipped: пропущено
        - pending: не отмечено
        - xp_earned: XP за день
    """
    total = len(steps)
    completed = sum(1 for s in steps if s.status == "completed")
    skipped = sum(1 for s in steps if s.status == "skipped")
    pending = sum(1 for s in steps if s.status == "pending")
    xp_earned = daily_log.xp_earned if daily_log else 0

    return {
        "total": total,
        "completed": completed,
        "skipped": skipped,
        "pending": pending,
        "xp_earned": xp_earned,
    }


def format_steps_summary(steps: list[Step]) -> str:
    """
    Форматировать список шагов с эмодзи-отметками.

    Args:
        steps: Список шагов дня

    Returns:
        Строка вида:
        ✅ Task 1
        ⏭ Task 2
        ⬜ Task 3
    """
    lines = []
    for step in steps:
        if step.status == "completed":
            icon = "✅"
        elif step.status == "skipped":
            icon = "⏭"
        else:
            icon = "⬜"
        lines.append(f"{icon} {step.title}")

    return "\n".join(lines)


def should_show_streak_celebration(streak_days: int) -> bool:
    """
    Определить, нужно ли показывать особое празднование streak.

    Args:
        streak_days: Количество дней подряд

    Returns:
        True если streak >= 3 (показываем "🔥 Streak: N дней подряд!")
        False если streak < 3 (показываем просто "🔥 Streak: N")
    """
    return streak_days >= 3


def format_streak_text(streak_days: int) -> str:
    """
    Форматировать текст streak для итогового сообщения.

    Args:
        streak_days: Количество дней подряд

    Returns:
        Строка вида:
        - "" (пусто) если streak == 0
        - "🔥 Streak: 1" если streak == 1-2
        - "🔥 Streak: 5 дней подряд!" если streak >= 3
    """
    if streak_days == 0:
        return ""

    if should_show_streak_celebration(streak_days):
        return f"\n🔥 *Streak: {streak_days} дней подряд!*"

    return f"\n🔥 Streak: {streak_days}"
