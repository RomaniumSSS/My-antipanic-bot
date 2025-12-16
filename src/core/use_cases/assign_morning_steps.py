"""
Assign Morning Steps Use Case - antipanic session flow.

AICODE-NOTE: This use-case orchestrates the antipanic morning flow:
1. Get active goal/stage
2. Create body micro-action step
3. Create task micro-action step
4. Log to DailyLog

Extracted from services/session.py for TMA migration.
"""

import logging
import random
from dataclasses import dataclass
from datetime import date

from src.core.domain.step_generation import (
    calculate_xp_for_step,
    energy_from_tension,
    select_step_difficulty,
)
from src.database.models import Goal, Stage, Step, User
from src.services.ai import ai_service
from src.storage import daily_log_repo, goal_repo, step_repo

logger = logging.getLogger(__name__)

# Predefined short body moves (2–3 minutes, low cognitive load)
BODY_ACTIONS: list[str] = [
    "Сделай 5 глубоких вдохов стоя, чувствуя стопы на полу",
    "Встряхни кисти и плечи 30 секунд, потом сделай пару кругов плечами",
    "Пройдися по комнате или коридору 2 минуты, считая шаги до 120",
    "Сделай растяжку: потянись вверх, потом к носкам, 3 раза",
    "Выпей стакан воды медленно, концентрируясь на ощущениях",
    "Сделай 10 лёгких приседаний или полуприседаний в удобном темпе",
    "Встань, расправь плечи и посмотри в окно 60 секунд, замечая детали",
]


@dataclass
class StageEnsureResult:
    """Result of ensuring active stage exists."""

    success: bool
    stage: Stage | None = None
    error_message: str = ""


@dataclass
class BodyStepResult:
    """Result of creating body micro-action step."""

    success: bool
    step: Step | None = None
    action_text: str = ""
    error_message: str = ""


@dataclass
class TaskStepResult:
    """Result of creating task micro-action step."""

    success: bool
    step: Step | None = None
    error_message: str = ""


class AssignMorningStepsUseCase:
    """Use-case for antipanic morning flow step assignment."""

    async def ensure_active_stage(self, goal: Goal) -> StageEnsureResult:
        """
        Ensure goal has exactly one active stage.

        Handles:
        - Multiple active stages (keeps latest, marks others pending)
        - Auto-complete stages at 100% progress (except onboarding goals)
        - Auto-activate next pending stage
        - Create default stage if none exist
        - Mark goal completed when all stages done

        Args:
            goal: Goal instance

        Returns:
            StageEnsureResult with active stage or error
        """
        # Get all active stages
        active_stages = await goal_repo.get_all_active_stages(goal)
        current = active_stages[0] if active_stages else None

        # Fix multiple active stages
        if len(active_stages) > 1:
            logger.warning(
                f"Goal {goal.id} has {len(active_stages)} active stages, keeping latest"
            )
            stale_stages = active_stages[1:]
            for stage in stale_stages:
                await goal_repo.update_stage_status(stage, "pending")

        # Auto-complete stage at 100% progress (except onboarding)
        if current and current.progress >= 100:
            if goal.status != "onboarding":
                current = await goal_repo.update_stage_status(current, "completed")
                current = None  # Need to find next stage
            # Onboarding goals keep adding steps to same stage

        # Activate next pending stage if current is None
        if not current:
            pending_stages = await goal_repo.get_pending_stages(goal)
            if pending_stages:
                current = await goal_repo.update_stage_status(
                    pending_stages[0], "active"
                )
            else:
                # No pending stages - check if goal is completed or needs default stage
                all_stages = await goal_repo.get_all_stages(goal)
                if not all_stages:
                    # No stages exist - create default
                    logger.warning(
                        f"Goal {goal.id} has no stages, creating default active stage"
                    )
                    start_date = goal.start_date or date.today()
                    end_date = goal.deadline or start_date
                    current = await goal_repo.create_stage(
                        goal=goal,
                        title="Стартовый этап",
                        order=1,
                        start_date=start_date,
                        end_date=end_date,
                        status="active",
                    )
                else:
                    # All stages exist, check if all completed
                    completed_count = sum(
                        1 for s in all_stages if s.status == "completed"
                    )
                    if (
                        completed_count == len(all_stages)
                        and goal.status != "onboarding"
                    ):
                        # Mark goal as completed
                        goal.status = "completed"
                        await goal_repo.save_goal(goal)
                        return StageEnsureResult(
                            success=False,
                            error_message="Все этапы цели завершены! Цель выполнена.",
                        )
                    # Should not reach here, but return error
                    return StageEnsureResult(
                        success=False,
                        error_message="Нет активных или ожидающих этапов",
                    )

        if not current:
            return StageEnsureResult(
                success=False,
                error_message="Не удалось получить активный этап",
            )

        return StageEnsureResult(success=True, stage=current)

    async def get_body_micro_action(self, user: User) -> str:
        """
        Pick a short grounding/activation action.

        Uses user's telegram_id as random seed for consistency.

        Args:
            user: User instance

        Returns:
            Body action text
        """
        random.seed(user.telegram_id)
        return random.choice(BODY_ACTIONS)

    async def create_body_step(
        self, user: User, goal: Goal, tension: int | None
    ) -> BodyStepResult:
        """
        Create body micro-action step for antipanic flow.

        Steps:
        1. Ensure active stage exists
        2. Pick body action
        3. Create step (2 min, easy, 3 XP)
        4. Log to DailyLog

        Args:
            user: User instance
            goal: Goal instance
            tension: Current tension level 0-10

        Returns:
            BodyStepResult with created step or error
        """
        # 1. Ensure active stage
        stage_result = await self.ensure_active_stage(goal)
        if not stage_result.success:
            return BodyStepResult(
                success=False,
                error_message=stage_result.error_message,
            )

        stage = stage_result.stage

        # 2. Pick body action
        action_text = await self.get_body_micro_action(user)

        # 3. Create step
        energy_hint = energy_from_tension(tension)
        step = await step_repo.create_step(
            stage_id=stage.id,
            title=action_text,
            difficulty="easy",
            estimated_minutes=2,
            xp_reward=3,
            scheduled_date=date.today(),
            status="pending",
        )

        # 4. Log to DailyLog
        daily_log = await daily_log_repo.get_or_create_daily_log(user, date.today())
        await daily_log_repo.log_step_assignment(
            daily_log=daily_log,
            step_id=step.id,
            energy_level=energy_hint,
            mood_text="body_action",
        )

        logger.info(
            f"Created body step {step.id} for user {user.telegram_id}: {action_text}"
        )

        return BodyStepResult(
            success=True,
            step=step,
            action_text=action_text,
        )

    async def create_task_micro_step(
        self,
        user: User,
        goal: Goal,
        tension: int | None = None,
        max_minutes: int = 5,
    ) -> TaskStepResult:
        """
        Create task micro-action step using AI.

        Steps:
        1. Ensure active stage exists
        2. Calculate energy and difficulty
        3. Generate step using AI
        4. Create step with appropriate XP
        5. Log to DailyLog

        Args:
            user: User instance
            goal: Goal instance
            tension: Current tension level 0-10
            max_minutes: Maximum step duration (default 5 for micro, 30 for deepen)

        Returns:
            TaskStepResult with created step or error
        """
        # 1. Ensure active stage
        stage_result = await self.ensure_active_stage(goal)
        if not stage_result.success:
            return TaskStepResult(
                success=False,
                error_message=stage_result.error_message,
            )

        stage = stage_result.stage

        # 2. Calculate energy and parameters
        energy_hint = energy_from_tension(tension)
        mood_hint = (
            f"antipanic:tension={tension}" if tension is not None else "antipanic"
        )
        difficulty = select_step_difficulty(energy_hint)

        # 3. Get daily_log for adaptive tone (plan 004)
        daily_log = await daily_log_repo.get_or_create_daily_log(user, date.today())

        # 4. Generate step using AI with adaptive tone
        try:
            if max_minutes <= 5:
                # Micro step (2-5 min)
                step_title = await ai_service.generate_micro_step(
                    stage_title=stage.title,
                    energy=energy_hint,
                    mood="включиться через микро",
                    user=user,
                    daily_log=daily_log,
                )
                minutes = max(2, min(max_minutes, 5))
                xp_reward = calculate_xp_for_step("easy", minutes)
                difficulty = "easy"
            else:
                # Longer sprint step (15-30 min)
                steps_data = await ai_service.generate_steps(
                    stage_title=stage.title,
                    energy=energy_hint,
                    mood="готов к короткому спринту",
                    user=user,
                    daily_log=daily_log,
                )
                # Pick first step that fits duration
                picked = next(
                    (s for s in steps_data if s.get("minutes", 30) <= max_minutes),
                    None,
                )
                if not picked and steps_data:
                    picked = steps_data[0]
                picked = picked or {
                    "title": "Сделать один продвинутый шаг",
                    "minutes": max_minutes,
                }

                step_title = picked.get("title", "Сделать шаг по этапу")
                difficulty = picked.get("difficulty", "medium")
                minutes = picked.get("minutes", max_minutes)
                xp_reward = calculate_xp_for_step(difficulty, minutes)

        except Exception as e:
            logger.error(f"Failed to generate task step via AI: {e}")
            return TaskStepResult(
                success=False,
                error_message=f"Не удалось сгенерировать шаг: {e}",
            )

        # 5. Create step
        step = await step_repo.create_step(
            stage_id=stage.id,
            title=step_title,
            difficulty=difficulty,
            estimated_minutes=minutes,
            xp_reward=xp_reward,
            scheduled_date=date.today(),
            status="pending",
        )

        # 6. Log to DailyLog (daily_log already fetched above for adaptive tone)
        await daily_log_repo.log_step_assignment(
            daily_log=daily_log,
            step_id=step.id,
            energy_level=energy_hint,
            mood_text=mood_hint,
        )

        logger.info(
            f"Created task step {step.id} for user {user.telegram_id}: "
            f"{step_title} ({minutes}min, {difficulty}, {xp_reward}XP)"
        )

        return TaskStepResult(success=True, step=step)


# Singleton instance
assign_morning_steps_use_case = AssignMorningStepsUseCase()
