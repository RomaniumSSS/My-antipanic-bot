"""
Stuck Resolution Domain Rules - pure functions for blocker logic.

AICODE-NOTE: This module contains pure domain functions without database access.
All business logic for stuck/blocker resolution is here.

Extracted from handlers/stuck.py for TMA migration Stage 2.3.
"""

from src.bot.callbacks.data import BlockerType

# Blocker descriptions for AI prompts
BLOCKER_DESCRIPTIONS: dict[BlockerType, str] = {
    BlockerType.fear: "страшно, тревожно браться за задачу",
    BlockerType.unclear: "не понимает с чего начать",
    BlockerType.no_time: "кажется что нет времени",
    BlockerType.no_energy: "нет сил и энергии",
}

# Emoji for UI representation
BLOCKER_EMOJIS: dict[str, str] = {
    "fear": "😨",
    "unclear": "🤷",
    "no_time": "⏰",
    "no_energy": "😴",
}


def get_blocker_description(blocker_type: BlockerType | str) -> str:
    """
    Get human-readable blocker description for AI prompts.

    Args:
        blocker_type: BlockerType enum or string value

    Returns:
        Description text for AI prompt

    Examples:
        >>> get_blocker_description(BlockerType.fear)
        "страшно, тревожно браться за задачу"
        >>> get_blocker_description("unclear")
        "не понимает с чего начать"
    """
    if isinstance(blocker_type, str):
        try:
            blocker_type = BlockerType(blocker_type)
        except ValueError:
            return blocker_type  # Return as-is if unknown

    return BLOCKER_DESCRIPTIONS.get(blocker_type, str(blocker_type))


def get_blocker_emoji(blocker_type: str) -> str:
    """
    Get emoji for blocker type.

    Args:
        blocker_type: Blocker type string

    Returns:
        Emoji character

    Examples:
        >>> get_blocker_emoji("fear")
        "😨"
        >>> get_blocker_emoji("unknown")
        "🔧"
    """
    return BLOCKER_EMOJIS.get(blocker_type, "🔧")


def is_valid_blocker(blocker_type: str) -> bool:
    """
    Check if blocker type is valid.

    Args:
        blocker_type: Blocker type string to validate

    Returns:
        True if valid BlockerType, False otherwise

    Examples:
        >>> is_valid_blocker("fear")
        True
        >>> is_valid_blocker("invalid")
        False
    """
    valid_types = [b.value for b in BlockerType]
    return blocker_type in valid_types


def normalize_blocker_type(blocker_type: BlockerType | str) -> BlockerType:
    """
    Normalize blocker type to BlockerType enum.

    Args:
        blocker_type: BlockerType enum or string value

    Returns:
        BlockerType enum (defaults to unclear if invalid)

    Examples:
        >>> normalize_blocker_type("fear")
        BlockerType.fear
        >>> normalize_blocker_type("invalid")
        BlockerType.unclear
    """
    if isinstance(blocker_type, BlockerType):
        return blocker_type

    try:
        return BlockerType(blocker_type)
    except ValueError:
        return BlockerType.unclear


def should_request_details(blocker_type: BlockerType) -> bool:
    """
    Determine if we should request additional details for this blocker type.

    Currently only "unclear" blocker requires details to generate better microhits.

    Args:
        blocker_type: The blocker type

    Returns:
        True if should request details, False otherwise

    Examples:
        >>> should_request_details(BlockerType.unclear)
        True
        >>> should_request_details(BlockerType.fear)
        False
    """
    return blocker_type == BlockerType.unclear


def calculate_microhit_count(blocker_type: BlockerType, has_details: bool) -> int:
    """
    Calculate how many microhit options to generate.

    Strategy:
    - With details: generate 2-3 options (more targeted)
    - Without details: generate 2-3 options (provide choice)

    Args:
        blocker_type: The blocker type
        has_details: Whether user provided additional details

    Returns:
        Number of microhit options to generate (2-3)

    Examples:
        >>> calculate_microhit_count(BlockerType.unclear, True)
        3
        >>> calculate_microhit_count(BlockerType.fear, False)
        2
    """
    # With details we can generate more targeted options
    if has_details:
        return 3

    # For simple blockers, 2 options is enough
    return 2
