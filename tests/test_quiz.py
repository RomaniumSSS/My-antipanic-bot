from src.bot.handlers.quiz import calculate_quiz_score


def test_quiz_score_zero_floor() -> None:
    """Weights with zero result in zero score and diff."""
    score, diff = calculate_quiz_score([{"weight": 0}])
    assert score == 0
    assert diff == 0


def test_quiz_score_mid_and_clamp() -> None:
    """Intermediate weight maps to 0-100 scale and diff is clamped at 0."""
    score, diff = calculate_quiz_score([{"weight": 16}])
    assert score == 50
    assert diff == 15

