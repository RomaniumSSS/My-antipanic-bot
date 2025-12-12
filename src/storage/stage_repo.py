"""
Stage Repository - тупые CRUD операции для Stage модели.

AICODE-NOTE: Репозиторий содержит только доступ к данным, БЕЗ бизнес-логики.
"""

from typing import Optional

from src.database.models import Stage


async def get_stage(stage_id: int) -> Optional[Stage]:
    """Получить этап по ID."""
    return await Stage.get_or_none(id=stage_id).prefetch_related("goal")


async def update_stage_progress(stage: Stage, progress: int) -> Stage:
    """Обновить прогресс этапа."""
    stage.progress = progress
    await stage.save()
    return stage


async def mark_stage_completed(stage: Stage) -> Stage:
    """Отметить этап как завершенный."""
    stage.status = "completed"
    await stage.save()
    return stage


async def mark_stage_active(stage: Stage) -> Stage:
    """Отметить этап как активный."""
    stage.status = "active"
    await stage.save()
    return stage


async def save_stage(stage: Stage) -> Stage:
    """Сохранить изменения этапа."""
    await stage.save()
    return stage
