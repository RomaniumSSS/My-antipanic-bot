"""
Step Generation Domain Rules - pure functions for step planning logic.

AICODE-NOTE: Pure functions without database access or side effects.
These rules are used by use-cases to determine step generation parameters.
"""

from typing import Literal


StepDifficulty = Literal["easy", "medium", "hard"]


def energy_from_tension(tension: int | None) -> int:
    """
    Convert tension level (0-10) to energy level (1-10).

    Rough mapping to keep energy_level populated for stats.
    Lower tension -> higher energy surrogate.

    Args:
        tension: Tension level 0-10 (0=calm, 10=panic) or None

    Returns:
        Energy level 1-10 (higher is better)
    """
    if tension is None:
        return 5
    # Inverse mapping: low tension = high energy
    return max(2, min(8, 10 - tension // 2))


def select_step_difficulty(energy: int) -> StepDifficulty:
    """
    Select appropriate step difficulty based on energy level.

    Rules:
    - Low energy (1-3): only easy steps
    - Medium energy (4-6): easy or medium steps
    - High energy (7-10): any difficulty

    Args:
        energy: Energy level 1-10

    Returns:
        Recommended difficulty: "easy", "medium", or "hard"
    """
    if energy <= 3:
        return "easy"
    if energy <= 6:
        return "medium"
    return "hard"


def calculate_max_step_duration(energy: int, is_micro: bool = False) -> int:
    """
    Calculate maximum step duration based on energy level.

    Rules:
    - Micro steps: 2-5 minutes (for antipanic flow)
    - Normal steps: 5-45 minutes based on energy

    Args:
        energy: Energy level 1-10
        is_micro: True for micro steps (antipanic), False for normal steps

    Returns:
        Maximum duration in minutes
    """
    if is_micro:
        # Micro steps are always short (2-5 min)
        return 5

    # Normal step durations based on energy
    if energy <= 3:
        return 10  # Low energy: max 10 minutes
    if energy <= 5:
        return 20  # Medium-low energy: max 20 minutes
    if energy <= 7:
        return 30  # Medium-high energy: max 30 minutes
    return 45  # High energy: up to 45 minutes


def calculate_xp_for_step(difficulty: StepDifficulty, duration_minutes: int) -> int:
    """
    Calculate XP reward for a step based on difficulty and duration.

    Base XP by difficulty:
    - easy: 10 XP
    - medium: 20 XP
    - hard: 40 XP

    Adjusted by duration:
    - Short (< 10 min): -50%
    - Normal (10-30 min): base
    - Long (> 30 min): +50%

    Args:
        difficulty: Step difficulty
        duration_minutes: Estimated duration in minutes

    Returns:
        XP reward
    """
    base_xp = {"easy": 10, "medium": 20, "hard": 40}
    xp = base_xp.get(difficulty, 20)

    # Adjust for duration
    if duration_minutes < 10:
        xp = int(xp * 0.5)
    elif duration_minutes > 30:
        xp = int(xp * 1.5)

    return max(3, xp)  # Minimum 3 XP


def should_offer_deepen(tension_before: int | None, tension_after: int | None) -> bool:
    """
    Decide whether to offer deepening (longer step) after antipanic session.

    Rules:
    - If tension decreased: likely to offer
    - If tension stayed same or increased: offer only if tension_after is low

    Args:
        tension_before: Tension level before action (0-10)
        tension_after: Tension level after action (0-10)

    Returns:
        True if should offer deepening option
    """
    if tension_before is None or tension_after is None:
        return True  # Default to offering

    # If tension decreased, always offer
    if tension_after < tension_before:
        return True

    # If tension stayed same or increased, only offer if final tension is low
    return tension_after <= 4


def calculate_steps_count_by_energy(energy: int) -> int:
    """
    Calculate recommended number of steps to assign based on energy level.

    Rules:
    - Low energy (1-3): 1-2 steps
    - Medium energy (4-6): 2-3 steps
    - High energy (7-10): 3-5 steps

    Args:
        energy: Energy level 1-10

    Returns:
        Number of steps to assign
    """
    if energy <= 3:
        return 2  # Low energy: just 1-2 steps
    if energy <= 6:
        return 3  # Medium energy: 2-3 steps
    return 4  # High energy: 3-5 steps
