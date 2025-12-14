"""
Complete Daily Reflection Use Case - вечерний итог дня.

AICODE-NOTE: This use-case orchestrates evening reflection flow:
1. Get daily summary (steps, stats)
2. Complete day (update streak, save user)

Extracted from handlers/evening.py for TMA migration Stage 2.4.
"""

import logging
from dataclasses import dataclass
from datetime import date

from src.core.domain.gamification import calculate_streak
from src.core.domain.reflection_rules import (
    calculate_daily_progress,
    format_steps_summary,
    format_streak_text,
)
from src.database.models import DailyLog, Step, User

logger = logging.getLogger(__name__)


@dataclass
class DailySummaryResult:
    """Result of getting daily summary."""

    success: bool
    daily_log: DailyLog | None = None
    steps: list[Step] | None = None
    progress: dict | None = None
    steps_text: str = ""
    has_pending: bool = False
    pending_step_ids: list[int] | None = None
    error_message: str = ""


@dataclass
class DayCompletionResult:
    """Result of completing the day."""

    success: bool
    steps_text: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    xp_earned: int = 0
    total_xp: int = 0
    streak_days: int = 0
    streak_text: str = ""
    streak_increased: bool = False
    error_message: str = ""


class CompleteDailyReflectionUseCase:
    """Use-case for evening reflection and day completion."""

    async def get_daily_summary(self, user: User, today: date) -> DailySummaryResult:
        """
        Get summary of the day - steps and progress.

        Steps:
        1. Get DailyLog for today
        2. Get steps from assigned_step_ids
        3. Calculate progress stats
        4. Format steps summary text

        Args:
            user: User instance
            today: Date to get summary for

        Returns:
            DailySummaryResult with steps, stats, and formatted text
        """
        # Get daily log
        daily_log = await DailyLog.get_or_none(user=user, date=today)

        if not daily_log or not daily_log.assigned_step_ids:
            return DailySummaryResult(
                success=False,
                error_message="Сегодня ещё не было старта дня. "
                "Сначала сделай короткий утренний чек-ин через кнопку «Утро».",
            )

        # Get steps
        steps = await Step.filter(id__in=daily_log.assigned_step_ids)

        if not steps:
            return DailySummaryResult(
                success=False,
                error_message="Не найдены шаги дня.",
            )

        # Calculate progress
        progress = calculate_daily_progress(daily_log, steps)

        # Format steps summary
        steps_text = format_steps_summary(steps)

        # Check for pending steps
        pending_steps = [s for s in steps if s.status == "pending"]
        has_pending = len(pending_steps) > 0
        pending_step_ids = [s.id for s in pending_steps] if has_pending else None

        return DailySummaryResult(
            success=True,
            daily_log=daily_log,
            steps=steps,
            progress=progress,
            steps_text=steps_text,
            has_pending=has_pending,
            pending_step_ids=pending_step_ids,
        )

    async def complete_day(self, user: User, today: date) -> DayCompletionResult:
        """
        Complete the day - update streak and finalize.

        Steps:
        1. Get daily summary
        2. Calculate new streak
        3. Update user (streak, save)
        4. Format completion message data

        Args:
            user: User instance
            today: Date to complete

        Returns:
            DayCompletionResult with completion data
        """
        # Get summary first
        summary = await self.get_daily_summary(user, today)

        if not summary.success:
            return DayCompletionResult(
                success=False,
                error_message=summary.error_message,
            )

        # Calculate new streak
        new_streak, streak_increased = calculate_streak(user, today)

        # Update user
        user.streak_days = new_streak
        user.streak_last_date = today
        await user.save()

        # Format streak text
        streak_text = format_streak_text(new_streak)

        # Get stats
        progress = summary.progress
        steps_text = summary.steps_text

        logger.info(
            f"Day completed for user {user.telegram_id}: "
            f"completed={progress['completed']}/{progress['total']}, "
            f"streak={new_streak} (increased={streak_increased})"
        )

        return DayCompletionResult(
            success=True,
            steps_text=steps_text,
            total_steps=progress["total"],
            completed_steps=progress["completed"],
            xp_earned=progress["xp_earned"],
            total_xp=user.xp,
            streak_days=new_streak,
            streak_text=streak_text,
            streak_increased=streak_increased,
        )


# Singleton instance
complete_daily_reflection_use_case = CompleteDailyReflectionUseCase()
