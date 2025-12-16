"""
Pydantic schemas for TMA API responses.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

# ============ User Schemas ============


class UserResponse(BaseModel):
    """User profile response."""

    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    username: str | None = None
    first_name: str | None = None

    # Gamification
    xp: int
    level: int
    streak_days: int

    # Settings
    reminder_morning: str
    reminder_evening: str
    timezone_offset: int
    reminders_enabled: bool


# ============ Goal Schemas ============


class StageResponse(BaseModel):
    """Stage within a goal."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    order: int
    start_date: date
    end_date: date
    progress: int
    status: str


class GoalListItem(BaseModel):
    """Goal item for list response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    deadline: date
    status: str
    created_at: datetime


class GoalDetailResponse(BaseModel):
    """Detailed goal response with stages."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    start_date: date
    deadline: date
    status: str
    stages: list[StageResponse]


class GoalsListResponse(BaseModel):
    """List of goals response."""

    goals: list[GoalListItem]
    total: int


# ============ Stats Schemas ============


class StatsResponse(BaseModel):
    """User statistics response."""

    # Gamification
    xp: int
    level: int
    xp_to_next_level: int
    streak_days: int

    # Progress
    total_goals: int
    active_goals: int
    completed_goals: int

    # Steps
    total_steps_completed: int
    steps_today: int

    # Calculated
    completion_rate: float  # 0.0 - 1.0


# ============ Step Schemas ============


class StepResponse(BaseModel):
    """Step item response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    difficulty: str
    estimated_minutes: int
    xp_reward: int
    scheduled_date: date | None = None
    status: str


class TodayStepsResponse(BaseModel):
    """Today's assigned steps."""

    steps: list[StepResponse]
    total_assigned: int
    completed: int


# ============ Step Action Schemas ============


class CompleteStepRequest(BaseModel):
    """Request to complete a step."""

    # No additional fields needed, step_id comes from path


class CompleteStepResponse(BaseModel):
    """Response after completing a step."""

    success: bool
    xp_earned: int
    total_xp: int
    streak_updated: bool
    new_streak: int


class SkipStepRequest(BaseModel):
    """Request to skip a step."""

    reason: str | None = "Не подошло"


class SkipStepResponse(BaseModel):
    """Response after skipping a step."""

    success: bool


# ============ MicroHit Schemas ============


class MicroHitRequest(BaseModel):
    """Request to generate micro-action for stuck state."""

    step_id: int
    blocker_text: str | None = None


class MicroHitResponse(BaseModel):
    """Generated micro-action response."""

    micro_action: str
    original_step: StepResponse
    estimated_minutes: int  # Usually 2-5 for micro-hit
