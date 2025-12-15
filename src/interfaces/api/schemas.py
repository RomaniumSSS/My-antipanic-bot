"""
Pydantic schemas for TMA API responses.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ============ User Schemas ============


class UserResponse(BaseModel):
    """User profile response."""

    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None

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
    description: Optional[str] = None
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
    scheduled_date: Optional[date] = None
    status: str


class TodayStepsResponse(BaseModel):
    """Today's assigned steps."""

    steps: list[StepResponse]
    total_assigned: int
    completed: int


# ============ MicroHit Schemas ============


class MicroHitRequest(BaseModel):
    """Request to generate micro-action for stuck state."""

    step_id: int
    blocker_text: Optional[str] = None


class MicroHitResponse(BaseModel):
    """Generated micro-action response."""

    micro_action: str
    original_step: StepResponse
    estimated_minutes: int  # Usually 2-5 for micro-hit
