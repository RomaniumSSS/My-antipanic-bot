"""
Step Repository - тупые CRUD операции для Step модели.

AICODE-NOTE: Репозиторий содержит только доступ к данным, БЕЗ бизнес-логики.
Бизнес-логика находится в core/domain и core/use_cases.
"""

from datetime import datetime
from typing import Optional

from src.database.models import Step


async def get_step(step_id: int) -> Optional[Step]:
    """Получить шаг по ID."""
    return await Step.get_or_none(id=step_id).prefetch_related("stage__goal")


async def get_steps_by_stage(stage_id: int) -> list[Step]:
    """Получить все шаги этапа."""
    return await Step.filter(stage_id=stage_id).all()


async def mark_completed(step: Step) -> Step:
    """Отметить шаг как выполненный."""
    step.status = "completed"
    step.completed_at = datetime.now()
    await step.save()
    return step


async def mark_skipped(step: Step) -> Step:
    """Отметить шаг как пропущенный."""
    step.status = "skipped"
    await step.save()
    return step


async def get_completed_count(stage_id: int) -> int:
    """Количество выполненных шагов в этапе."""
    return await Step.filter(stage_id=stage_id, status="completed").count()


async def get_total_count(stage_id: int) -> int:
    """Общее количество шагов в этапе."""
    return await Step.filter(stage_id=stage_id).count()


async def get_finished_count(stage_id: int) -> int:
    """Количество завершенных шагов (completed или skipped)."""
    return await Step.filter(
        stage_id=stage_id, status__in=["completed", "skipped"]
    ).count()
