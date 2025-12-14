"""
DailyLog Repository - тупые CRUD операции для DailyLog модели.

AICODE-NOTE: Репозиторий содержит только доступ к данным, БЕЗ бизнес-логики.
"""

from datetime import date

from src.database.models import DailyLog, Step, User


async def get_or_create_daily_log(user: User, log_date: date) -> DailyLog:
    """Получить или создать DailyLog за указанную дату."""
    daily_log, _ = await DailyLog.get_or_create(user=user, date=log_date)
    return daily_log


async def get_daily_log(user: User, log_date: date) -> DailyLog | None:
    """Получить DailyLog за указанную дату."""
    return await DailyLog.get_or_none(user=user, date=log_date)


async def log_step_completion(
    daily_log: DailyLog, step: Step, xp_earned: int
) -> DailyLog:
    """Добавить выполненный шаг в DailyLog."""
    completed = daily_log.completed_step_ids or []
    if step.id not in completed:
        completed.append(step.id)
        daily_log.completed_step_ids = completed
        daily_log.xp_earned = (daily_log.xp_earned or 0) + xp_earned
        await daily_log.save()
    return daily_log


async def log_step_skip(daily_log: DailyLog, step_id: int, reason: str) -> DailyLog:
    """Добавить пропущенный шаг в DailyLog."""
    skip_reasons = daily_log.skip_reasons or {}
    skip_reasons[str(step_id)] = reason
    daily_log.skip_reasons = skip_reasons
    await daily_log.save()
    return daily_log


async def log_step_assignment(
    daily_log: DailyLog,
    step_id: int,
    energy_level: int | None = None,
    mood_text: str | None = None,
) -> DailyLog:
    """
    Добавить назначенный шаг в DailyLog.

    Args:
        daily_log: DailyLog instance
        step_id: ID назначенного шага
        energy_level: Уровень энергии (опционально)
        mood_text: Настроение (опционально)

    Returns:
        Updated DailyLog
    """
    assigned = daily_log.assigned_step_ids or []
    if step_id not in assigned:
        assigned.append(step_id)
        daily_log.assigned_step_ids = assigned

    if energy_level is not None and daily_log.energy_level is None:
        daily_log.energy_level = energy_level

    if mood_text and not daily_log.mood_text:
        daily_log.mood_text = mood_text

    await daily_log.save()
    return daily_log


async def save_daily_log(daily_log: DailyLog) -> DailyLog:
    """Сохранить изменения DailyLog."""
    await daily_log.save()
    return daily_log
