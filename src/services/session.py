"""
Session helpers for the antipanic /morning flow.

Responsibilities:
- Provide quick body micro-actions.
- Generate short task micro-actions using existing AI logic.
- Ensure steps are logged into DailyLog so evening/weekly/status keep working.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Iterable
from datetime import date

from src.database.models import DailyLog, Goal, Stage, Step, User
from src.services.ai import ai_service

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


def _energy_from_tension(tension: int | None) -> int:
    """
    Rough mapping to keep energy_level populated for stats.
    Lower tension -> a bit higher energy surrogate.
    """
    if tension is None:
        return 5
    return max(2, min(8, 10 - tension // 2))


async def ensure_active_stage(goal: Goal) -> Stage | None:
    """
    Return current active stage for a goal.
    If active is completed (>=100) mark it completed and activate next pending.
    """
    active_stages = (
        await Stage.filter(goal=goal, status="active").order_by("-order", "-id").all()
    )
    current = active_stages[0] if active_stages else None

    if len(active_stages) > 1:
        logger.warning(
            "Goal %s has multiple active stages, keeping the latest", goal.id
        )
        stale_ids = [stage.id for stage in active_stages[1:]]
        await Stage.filter(id__in=stale_ids).update(status="pending")

    if current and current.progress >= 100:
        # Для онбординговых целей даём возможность добавлять ещё шаги,
        # не завершая этап после первого же микрошага.
        if goal.status != "onboarding":
            current.status = "completed"
            await current.save()
            current = None

    if not current:
        current = (
            await Stage.filter(goal=goal, status="pending").order_by("order").first()
        )
        if current:
            current.status = "active"
            await current.save()
        else:
            total = await Stage.filter(goal=goal).count()
            if total == 0:
                start_date = goal.start_date or date.today()
                end_date = goal.deadline or start_date
                logger.warning(
                    "Goal %s has no stages, creating default active stage", goal.id
                )
                current = await Stage.create(
                    goal=goal,
                    title="Стартовый этап",
                    order=1,
                    start_date=start_date,
                    end_date=end_date,
                    progress=0,
                    status="active",
                )
            else:
                completed = await Stage.filter(goal=goal, status="completed").count()
                if total and completed == total and goal.status != "onboarding":
                    goal.status = "completed"
                    await goal.save()
    return current


async def log_antipanic_action(
    *,
    user: User,
    step: Step,
    energy_hint: int | None = None,
    mood_hint: str | None = None,
    completed: bool = False,
) -> None:
    """
    Attach a step to today's DailyLog so stats remain consistent.
    Optionally mark it as completed immediately.
    """
    today = date.today()
    daily_log, _ = await DailyLog.get_or_create(
        user=user,
        date=today,
        defaults={
            "energy_level": energy_hint or 5,
            "mood_text": mood_hint or "antipanic",
            "assigned_step_ids": [step.id],
            "completed_step_ids": [step.id] if completed else [],
            "xp_earned": step.xp_reward if completed else 0,
        },
    )

    assigned = set(daily_log.assigned_step_ids or [])
    if step.id not in assigned:
        assigned.add(step.id)
        daily_log.assigned_step_ids = list(assigned)

    if completed:
        completed_ids = set(daily_log.completed_step_ids or [])
        if step.id not in completed_ids:
            completed_ids.add(step.id)
            daily_log.completed_step_ids = list(completed_ids)
            daily_log.xp_earned = (daily_log.xp_earned or 0) + step.xp_reward

    if daily_log.energy_level is None:
        daily_log.energy_level = energy_hint or 5
    if mood_hint and not daily_log.mood_text:
        daily_log.mood_text = mood_hint

    await daily_log.save()


async def _create_step(
    *,
    stage: Stage,
    title: str,
    minutes: int,
    difficulty: str,
    xp_reward: int,
    user: User,
    energy_hint: int | None,
    mood_hint: str | None,
) -> Step:
    step = await Step.create(
        stage=stage,
        title=title,
        difficulty=difficulty,
        estimated_minutes=minutes,
        xp_reward=xp_reward,
        scheduled_date=date.today(),
        status="pending",
    )
    await log_antipanic_action(
        user=user, step=step, energy_hint=energy_hint, mood_hint=mood_hint
    )
    return step


async def get_body_micro_action(user: User) -> str:
    """Pick a short grounding/activation action."""
    random.seed(user.telegram_id)
    return random.choice(BODY_ACTIONS)


async def create_body_step(
    *, user: User, goal: Goal, action_text: str, tension: int | None
) -> Step:
    """Create a logged body-oriented micro-step attached to the active stage."""
    stage = await ensure_active_stage(goal)
    if not stage:
        raise ValueError("No active stage available for goal")

    energy_hint = _energy_from_tension(tension)
    return await _create_step(
        stage=stage,
        title=action_text,
        minutes=2,
        difficulty="easy",
        xp_reward=3,
        user=user,
        energy_hint=energy_hint,
        mood_hint="body_action",
    )


async def get_task_micro_action(
    *, user: User, goal: Goal, tension: int | None = None, max_minutes: int = 5
) -> Step:
    """
    Generate or select a short task step tied to the current stage.
    Uses existing AI logic, keeps durations tiny by default.
    """
    stage = await ensure_active_stage(goal)
    if not stage:
        raise ValueError("No active stage available for goal")

    energy_hint = _energy_from_tension(tension)
    mood_hint = f"antipanic:tension={tension}" if tension is not None else "antipanic"

    if max_minutes <= 5:
        text = await ai_service.generate_micro_step(
            stage_title=stage.title, energy=energy_hint, mood="включиться через микро"
        )
        minutes = max(2, min(max_minutes, 5))
        xp_reward = 5
        difficulty = "easy"
        return await _create_step(
            stage=stage,
            title=text,
            minutes=minutes,
            difficulty=difficulty,
            xp_reward=xp_reward,
            user=user,
            energy_hint=energy_hint,
            mood_hint=mood_hint,
        )

    # Longer sprint offer: take first AI suggestion that fits duration
    steps_data = await ai_service.generate_steps(
        stage_title=stage.title, energy=energy_hint, mood="готов к короткому спринту"
    )
    picked = next((s for s in steps_data if s.get("minutes", 30) <= max_minutes), None)
    if not picked and steps_data:
        picked = steps_data[0]
    picked = picked or {"title": "Сделать один продвинутый шаг", "minutes": max_minutes}

    difficulty = picked.get("difficulty", "medium")
    minutes = picked.get("minutes", max_minutes)
    xp_map = {"easy": 10, "medium": 20, "hard": 40}
    xp_reward = xp_map.get(difficulty, 20)

    return await _create_step(
        stage=stage,
        title=picked.get("title", "Сделать шаг по этапу"),
        minutes=minutes,
        difficulty=difficulty,
        xp_reward=xp_reward,
        user=user,
        energy_hint=energy_hint,
        mood_hint=mood_hint,
    )


def support_message(*, before: int | None = None, after: int | None = None) -> str:
    """Short supportive phrase after action."""
    if before is not None and after is not None:
        delta = before - after
        if delta > 0:
            return f"Вижу сдвиг: напряжение ↓ на {delta}. Отлично!"
        if delta == 0:
            return "Ты держишься стабильно — уже победа, двигаемся дальше."
        return "Даже если стало чуть тревожнее, ты всё равно сделал шаг. Это важно."
    return "Круто, что сделал действие — мозг уже переключается."


def format_steps_preview(steps: Iterable[Step]) -> str:
    """Helper to show a compact list of steps."""
    lines = []
    for s in steps:
        icon = "✅" if s.status == "completed" else "⬜"
        lines.append(f"{icon} {s.title}")
    return "\n".join(lines)
