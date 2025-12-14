"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ===== User Schemas =====


class UserProfileResponse(BaseModel):
    """User profile data."""

    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    xp: int = 0
    level: int = 1
    streak_days: int = 0
    timezone_offset: int = 0

    class Config:
        from_attributes = True


# ===== Goal Schemas =====


class GoalResponse(BaseModel):
    """Active goal data."""

    id: int
    title: str
    current_stage: Optional[str] = None
    progress: int = 0
    deadline: Optional[str] = None

    class Config:
        from_attributes = True


# ===== Microhit Schemas =====


class MicrohitGenerateRequest(BaseModel):
    """Request to generate microhit options."""

    step_title: str = Field(..., description="Title of the stuck step")
    blocker_type: str = Field(
        ..., description="Type of blocker: fear, overwhelm, unclear, distraction"
    )
    details: Optional[str] = Field(None, description="Additional details about blocker")


class MicrohitOption(BaseModel):
    """Single microhit option."""

    index: int = Field(..., description="Option index (0-based)")
    text: str = Field(..., description="Microhit text")


class MicrohitGenerateResponse(BaseModel):
    """Response with microhit options."""

    options: List[MicrohitOption]
    step_id: int = Field(..., description="Created step ID for tracking")


class MicrohitCompleteRequest(BaseModel):
    """Request to complete a microhit."""

    step_id: int = Field(..., description="Step ID to mark as completed")


class MicrohitCompleteResponse(BaseModel):
    """Response after completing a microhit."""

    xp_earned: int
    total_xp: int
    streak_days: int
    level: int


# ===== Stats Schemas =====


class TodayStatsResponse(BaseModel):
    """Today's statistics."""

    energy_level: Optional[int] = None
    steps_assigned: int = 0
    steps_completed: int = 0
    xp_earned: int = 0


class WeekStatsResponse(BaseModel):
    """Week statistics."""

    active_days: int = 0
    total_xp: int = 0
    total_steps: int = 0


class StatsResponse(BaseModel):
    """Full statistics response."""

    today: TodayStatsResponse
    week: WeekStatsResponse


# ===== History Schemas =====


class StepHistoryItem(BaseModel):
    """Single step in history."""

    id: int
    title: str
    completed_at: Optional[datetime] = None
    xp_reward: int = 0
    difficulty: str

    class Config:
        from_attributes = True


class HistoryResponse(BaseModel):
    """History of completed steps."""

    steps: List[StepHistoryItem]
