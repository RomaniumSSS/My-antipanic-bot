"""
Step Rules Domain - чистые правила валидации для шагов.

AICODE-NOTE: Чистые функции БЕЗ доступа к БД, БЕЗ side-effects.
Определяют можно ли выполнить/пропустить шаг.
"""

from src.database.models import Step


def can_complete_step(step: Step) -> bool:
    """
    Проверить, можно ли отметить шаг выполненным.

    Правила:
    - Шаг должен быть в статусе "pending"
    """
    return step.status == "pending"


def can_skip_step(step: Step) -> bool:
    """
    Проверить, можно ли пропустить шаг.

    Правила:
    - Шаг должен быть в статусе "pending"
    """
    return step.status == "pending"


def is_step_finished(step: Step) -> bool:
    """Проверить, завершен ли шаг (completed или skipped)."""
    return step.status in ("completed", "skipped")
