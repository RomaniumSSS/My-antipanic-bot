"""
Skip Step Use Case - сценарий пропуска шага.

AICODE-NOTE: Use-case объединяет репозитории + домейн-правила.
Handlers вызывают use-case и получают результат.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.core.domain.step_rules import can_skip_step
from src.database.models import User
from src.storage import daily_log_repo, step_repo

logger = logging.getLogger(__name__)


@dataclass
class StepSkipResult:
    """Результат пропуска шага."""

    success: bool
    error_message: str = ""


class SkipStepUseCase:
    """Use-case для пропуска шага."""

    async def execute(
        self,
        step_id: int,
        user: User,
        reason: str = "-",
        today: Optional[date] = None,
    ) -> StepSkipResult:
        """
        Пропустить шаг.

        Args:
            step_id: ID шага
            user: Пользователь
            reason: Причина пропуска
            today: Дата (для тестов, по умолчанию date.today())

        Returns:
            StepSkipResult с результатом операции
        """
        if today is None:
            today = date.today()

        # 1. Получить шаг
        step = await step_repo.get_step(step_id)
        if not step:
            return StepSkipResult(success=False, error_message="Шаг не найден")

        # 2. Проверить правила (домейн)
        if not can_skip_step(step):
            return StepSkipResult(
                success=False,
                error_message=f"Шаг уже завершен (статус: {step.status})",
            )

        # 3. Обновить шаг (репозиторий)
        await step_repo.mark_skipped(step)

        # 4. Обновить прогресс этапа
        await self._update_stage_progress(step.stage_id)

        # 5. Обновить DailyLog (репозиторий)
        daily_log = await daily_log_repo.get_or_create_daily_log(user, today)
        await daily_log_repo.log_step_skip(daily_log, step_id, reason)

        logger.info(
            f"Step {step_id} skipped by user {user.telegram_id}: {reason}"
        )

        return StepSkipResult(success=True)

    async def _update_stage_progress(self, stage_id: int) -> None:
        """
        Обновить прогресс этапа на основе выполненных шагов.

        Логика та же что в CompleteStepUseCase (может быть вынесена в отдельный сервис).
        """
        from src.storage import stage_repo

        try:
            # Получаем все шаги этапа
            all_steps = await step_repo.get_steps_by_stage(stage_id)
            total_count = len(all_steps)

            if total_count == 0:
                logger.warning(
                    f"Stage {stage_id} has no steps, skipping progress update"
                )
                return

            # Считаем выполненные шаги
            completed_count = sum(
                1 for s in all_steps if s.status == "completed"
            )

            # Рассчитываем прогресс
            new_progress = int((completed_count / total_count) * 100)

            # Получаем этап
            stage = await stage_repo.get_stage(stage_id)
            if not stage:
                logger.error(f"Stage {stage_id} not found")
                return

            stage.progress = new_progress

            # Проверяем, все ли шаги завершены
            finished_count = sum(
                1 for s in all_steps if s.status in ("completed", "skipped")
            )

            # Загружаем goal через await stage.goal
            await stage.fetch_related("goal")
            goal = stage.goal

            if finished_count == total_count and completed_count > 0:
                if goal.status != "onboarding":
                    stage.status = "completed"
                else:
                    stage.status = "active"
            elif stage.status == "pending" and completed_count > 0:
                stage.status = "active"

            await stage_repo.save_stage(stage)

            logger.info(
                f"Stage {stage_id} progress updated: {new_progress}% "
                f"({completed_count}/{total_count})"
            )
        except Exception as e:
            logger.error(
                f"Failed to update stage progress for stage {stage_id}: {e}"
            )
