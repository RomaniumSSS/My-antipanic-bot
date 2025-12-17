"""Tests for type-safe Markdown formatter."""

from src.bot.formatters import MarkdownFormatter, md


def test_bold_escapes_special_chars() -> None:
    """Bold formatter should escape markdown special characters."""
    formatter = MarkdownFormatter()

    # Test with underscores
    assert formatter.bold("My_Goal") == "*My\\_Goal*"

    # Test with asterisks
    assert formatter.bold("Step*2") == "*Step\\*2*"

    # Test with brackets
    assert formatter.bold("Task[1]") == "*Task\\[1\\]*"


def test_bold_joins_multiple_parts() -> None:
    """Bold should join multiple parts with spaces."""
    formatter = MarkdownFormatter()

    assert formatter.bold("Goal:", "My_Goal") == "*Goal: My\\_Goal*"
    assert formatter.bold("XP:", 100) == "*XP: 100*"


def test_italic_escapes_special_chars() -> None:
    """Italic formatter should escape markdown special characters."""
    formatter = MarkdownFormatter()

    assert formatter.italic("Stage_1") == "_Stage\\_1_"
    assert formatter.italic("Part*2") == "_Part\\*2_"


def test_code_no_escaping() -> None:
    """Code blocks don't need escaping in Telegram."""
    formatter = MarkdownFormatter()

    # Special chars should NOT be escaped in code
    assert formatter.code("my_function()") == "`my_function()`"
    assert formatter.code("*bold*") == "`*bold*`"


def test_text_escapes_without_formatting() -> None:
    """Text should escape but not apply formatting."""
    formatter = MarkdownFormatter()

    assert formatter.text("My_Text") == "My\\_Text"
    assert formatter.text("Part 1", "Part*2") == "Part 1 Part\\*2"


def test_link_escapes_text_not_url() -> None:
    """Links should escape text but not URL."""
    formatter = MarkdownFormatter()

    result = formatter.link("My_Link", "https://example.com")
    assert result == "[My\\_Link](https://example.com)"


def test_global_instance() -> None:
    """Global md instance should work."""
    # Test that global instance works
    assert md.bold("Test") == "*Test*"
    assert md.italic("Test") == "_Test_"


def test_handles_numbers() -> None:
    """Should handle numeric types."""
    formatter = MarkdownFormatter()

    assert formatter.bold("XP:", 100) == "*XP: 100*"
    assert formatter.text("Progress:", 75.5) == "Progress: 75.5"  # . is not special


def test_empty_input() -> None:
    """Should handle empty input gracefully."""
    formatter = MarkdownFormatter()

    assert formatter.bold() == "**"  # Empty but valid markdown
    assert formatter.italic() == "__"
    assert formatter.text() == ""


def test_all_special_chars_escaped() -> None:
    """All Telegram markdown special chars should be escaped."""
    formatter = MarkdownFormatter()

    # All special chars: _ * [ ] ( ) ~ ` > # + - = | { }
    text_with_all_chars = "_*[]()~`>#+-=|{}"
    result = formatter.text(text_with_all_chars)

    # Check each char is escaped
    assert "\\_" in result
    assert "\\*" in result
    assert "\\[" in result
    assert "\\]" in result
    assert "\\(" in result
    assert "\\)" in result
    assert "\\~" in result
    assert "\\`" in result
    assert "\\>" in result
    assert "\\#" in result
    assert "\\+" in result
    assert "\\-" in result
    assert "\\=" in result
    assert "\\|" in result
    assert "\\{" in result
    assert "\\}" in result
