"""
Complete Step Use Case - сценарий выполнения шага.

AICODE-NOTE: Use-case объединяет репозитории + домейн-правила.
Handlers вызывают use-case и получают результат.
"""

import logging
from dataclasses import dataclass
from datetime import date

from src.core.domain.gamification import calculate_streak, calculate_xp_reward
from src.core.domain.step_rules import can_complete_step
from src.database.models import User
from src.storage import daily_log_repo, stage_repo, step_repo, user_repo

logger = logging.getLogger(__name__)


@dataclass
class StepCompletionResult:
    """Результат выполнения шага."""

    success: bool
    xp_earned: int = 0
    total_xp: int = 0
    streak_updated: bool = False
    new_streak: int = 0
    error_message: str = ""


class CompleteStepUseCase:
    """Use-case для выполнения шага."""

    async def execute(
        self, step_id: int, user: User, today: date | None = None
    ) -> StepCompletionResult:
        """
        Выполнить шаг.

        Args:
            step_id: ID шага
            user: Пользователь
            today: Дата (для тестов, по умолчанию date.today())

        Returns:
            StepCompletionResult с результатом операции
        """
        if today is None:
            today = date.today()

        # 1. Получить шаг
        step = await step_repo.get_step(step_id)
        if not step:
            return StepCompletionResult(success=False, error_message="Шаг не найден")

        # 2. Проверить правила (домейн)
        if not can_complete_step(step):
            return StepCompletionResult(
                success=False,
                error_message=f"Шаг уже завершен (статус: {step.status})",
            )

        # 3. Рассчитать XP (домейн)
        xp_earned = calculate_xp_reward(step)

        # 4. Рассчитать streak (домейн)
        new_streak, streak_updated = calculate_streak(user, today)

        # 5. Обновить шаг (репозиторий)
        await step_repo.mark_completed(step)

        # 6. Обновить прогресс этапа
        # AICODE-NOTE: stage_id создаётся Tortoise ORM динамически для ForeignKeyField
        await self._update_stage_progress(step.stage_id)  # type: ignore[attr-defined]

        # 7. Обновить DailyLog (репозиторий)
        daily_log = await daily_log_repo.get_or_create_daily_log(user, today)
        await daily_log_repo.log_step_completion(daily_log, step, xp_earned)

        # 8. Обновить пользователя (репозиторий)
        user = await user_repo.update_xp(user, xp_earned)

        if streak_updated:
            user.streak_last_date = today
            user = await user_repo.update_streak(user, new_streak)

        logger.info(
            f"Step {step_id} completed by user {user.telegram_id}: +{xp_earned} XP"
        )

        return StepCompletionResult(
            success=True,
            xp_earned=xp_earned,
            total_xp=user.xp,
            streak_updated=streak_updated,
            new_streak=new_streak,
        )

    async def _update_stage_progress(self, stage_id: int) -> None:
        """
        Обновить прогресс этапа на основе выполненных шагов.

        Логика из steps.py:update_stage_progress().
        """
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
            completed_count = sum(1 for s in all_steps if s.status == "completed")

            # Рассчитываем прогресс
            new_progress = int((completed_count / total_count) * 100)

            # Получаем этап и цель
            stage = await stage_repo.get_stage(stage_id)
            if not stage:
                logger.error(f"Stage {stage_id} not found")
                return

            stage.progress = new_progress

            # Проверяем, все ли шаги завершены
            finished_count = sum(
                1 for s in all_steps if s.status in ("completed", "skipped")
            )

            # Загружаем goal через await stage.goal (Tortoise ORM relation)
            await stage.fetch_related("goal")
            goal = stage.goal

            # AICODE-NOTE: Не завершаем stage если шагов мало (antipanic micro-steps)
            # Иначе цель завершается после первого body_step (1/1 = 100%)
            # Минимум 4 шага для авто-завершения этапа
            MIN_STEPS_FOR_AUTO_COMPLETE = 4

            if finished_count == total_count and completed_count > 0:
                if goal.status != "onboarding" and total_count >= MIN_STEPS_FOR_AUTO_COMPLETE:
                    stage.status = "completed"
                else:
                    # Мало шагов или onboarding — держим active для продолжения
                    stage.status = "active"
            elif stage.status == "pending" and completed_count > 0:
                stage.status = "active"

            await stage_repo.save_stage(stage)

            logger.info(
                f"Stage {stage_id} progress updated: {new_progress}% "
                f"({completed_count}/{total_count})"
            )
        except Exception as e:
            logger.error(f"Failed to update stage progress for stage {stage_id}: {e}")
