"""
Resolve Stuck Use Case - generate microhit options for blocked users.

AICODE-NOTE: This use-case orchestrates stuck resolution flow:
1. Determine blocker type and context
2. Generate multiple microhit options (not just one!)
3. User picks preferred option
4. (Optional) Create step for selected microhit

Extracted from handlers/stuck.py for TMA migration Stage 2.3.
Optimized in plan 003 to use get_microhit_variants() for single API call.
"""

import logging
from dataclasses import dataclass
from datetime import date

from src.bot.callbacks.data import BlockerType
from src.core.domain.stuck_rules import (
    calculate_microhit_count,
    get_blocker_description,
    normalize_blocker_type,
)
from src.database.models import DailyLog, Goal, Stage, Step, User
from src.services.ai import ai_service
from src.storage import goal_repo

logger = logging.getLogger(__name__)


@dataclass
class MicrohitOption:
    """Single microhit option."""

    text: str
    index: int  # 1-based for display


@dataclass
class MicrohitOptionsResult:
    """Result of generating microhit options."""

    success: bool
    options: list[MicrohitOption] = None
    error_message: str = ""


@dataclass
class StuckContextResult:
    """Result of getting stuck context."""

    success: bool
    step_title: str = ""
    step_id: int | None = None
    stage: Stage | None = None
    error_message: str = ""


class ResolveStuckUseCase:
    """Use-case for resolving stuck/blocker situations."""

    async def get_stuck_context(self, user: User, goal: Goal) -> StuckContextResult:
        """
        Get context for stuck resolution - current step or stage title.

        Steps:
        1. Get active stage for goal
        2. Check today's DailyLog for pending steps
        3. Return step title/id for context

        Args:
            user: User instance
            goal: Active goal instance

        Returns:
            StuckContextResult with step/stage context
        """
        # Get active stage
        stage = await goal_repo.get_active_stage(goal)
        if not stage:
            return StuckContextResult(
                success=False,
                error_message="Нет активного этапа для цели",
            )

        # Check today's pending steps
        today = date.today()
        daily_log = await DailyLog.get_or_none(user=user, date=today)

        step_title = stage.title  # Fallback to stage title
        step_id = None

        if daily_log and daily_log.assigned_step_ids:
            # Get first pending step
            steps = await Step.filter(
                id__in=daily_log.assigned_step_ids, status="pending"
            )
            if steps:
                first_step = steps[0]
                step_title = first_step.title
                step_id = first_step.id

        return StuckContextResult(
            success=True,
            step_title=step_title,
            step_id=step_id,
            stage=stage,
        )

    async def generate_microhit_options(
        self,
        step_title: str,
        blocker_type: BlockerType | str,
        details: str = "",
        count: int | None = None,
    ) -> MicrohitOptionsResult:
        """
        Generate multiple microhit options for user to choose from.

        This is a KEY IMPROVEMENT in Stage 2.3: instead of showing one microhit
        and forcing user to request "more", we generate 2-3 options upfront.

        Strategy:
        - Generate count microhits in parallel (concurrent AI calls)
        - Each microhit is independent (different approach to same problem)
        - User picks the one that resonates most

        Args:
            step_title: Title of step/task user is stuck on
            blocker_type: Type of blocker (fear/unclear/no_time/no_energy)
            details: Additional context from user (optional)
            count: Number of options to generate (default: auto-calculate)

        Returns:
            MicrohitOptionsResult with list of options or error
        """
        # Normalize blocker type
        blocker = normalize_blocker_type(blocker_type)
        blocker_desc = get_blocker_description(blocker)

        # Calculate how many options to generate
        if count is None:
            count = calculate_microhit_count(blocker, bool(details))

        logger.info(
            f"Generating {count} microhit options for step='{step_title}' "
            f"blocker='{blocker.value}' details='{details[:50]}'"
        )

        try:
            # AICODE-NOTE: Optimized in plan 003 - single API call instead of N parallel calls
            # Use get_microhit_variants() for efficient variant generation
            microhits = await ai_service.get_microhit_variants(
                step_title=step_title,
                blocker_type=blocker_desc,
                details=details,
                count=count,
            )

            # Create options from results
            options = [
                MicrohitOption(text=text, index=i)
                for i, text in enumerate(microhits, start=1)
            ]

            if not options:
                return MicrohitOptionsResult(
                    success=False,
                    error_message="Не удалось сгенерировать варианты микро-ударов",
                )

            logger.info(f"Successfully generated {len(options)} microhit options")

            return MicrohitOptionsResult(success=True, options=options)

        except Exception as e:
            logger.exception(f"Failed to generate microhit options: {e}")
            return MicrohitOptionsResult(
                success=False,
                error_message=f"Ошибка генерации: {e}",
            )


# Singleton instance
resolve_stuck_use_case = ResolveStuckUseCase()
