"""
Type-safe Telegram Markdown formatter.

Автоматически экранирует специальные символы при форматировании,
предотвращая ошибки парсинга entities.
"""

from src.bot.utils import escape_markdown


class MarkdownFormatter:
    """
    Type-safe Telegram markdown formatter with automatic escaping.

    Все методы автоматически экранируют специальные символы,
    поэтому невозможно забыть вызвать escape_markdown().

    Usage:
        from src.bot.formatters import md

        # Вместо:
        text = f"Goal: *{escape_markdown(goal.title)}*"

        # Используйте:
        text = f"Goal: {md.bold(goal.title)}"
    """

    @staticmethod
    def bold(*parts: str | int | float) -> str:
        """
        Format text as bold with auto-escaping.

        Args:
            *parts: Text parts to join and format as bold

        Returns:
            Formatted text: *escaped_text*

        Example:
            md.bold("Goal:", goal.title)  # "Goal: My_Goal" -> "*Goal: My\\_Goal*"
        """
        escaped = " ".join(escape_markdown(str(p)) for p in parts)
        return f"*{escaped}*"

    @staticmethod
    def italic(*parts: str | int | float) -> str:
        """
        Format text as italic with auto-escaping.

        Args:
            *parts: Text parts to join and format as italic

        Returns:
            Formatted text: _escaped_text_

        Example:
            md.italic("Stage:", stage.title)
        """
        escaped = " ".join(escape_markdown(str(p)) for p in parts)
        return f"_{escaped}_"

    @staticmethod
    def code(text: str) -> str:
        """
        Format text as inline code.

        Args:
            text: Text to format as code

        Returns:
            Formatted text: `text`

        Note:
            Code blocks don't need escaping in Telegram.
        """
        return f"`{text}`"

    @staticmethod
    def text(*parts: str | int | float) -> str:
        """
        Plain text with automatic escaping.

        Args:
            *parts: Text parts to join and escape

        Returns:
            Escaped text without formatting

        Example:
            md.text("Some text with", special_chars)
        """
        return " ".join(escape_markdown(str(p)) for p in parts)

    @staticmethod
    def link(text: str, url: str) -> str:
        """
        Format as markdown link.

        Args:
            text: Link text (will be escaped)
            url: URL (will NOT be escaped)

        Returns:
            Formatted link: [escaped_text](url)

        Example:
            md.link("Claude Code", "https://claude.com/code")
        """
        escaped_text = escape_markdown(text)
        return f"[{escaped_text}]({url})"


# Global singleton instance for convenient import
md = MarkdownFormatter()
