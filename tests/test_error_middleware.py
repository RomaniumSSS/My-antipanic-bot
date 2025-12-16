"""Test error handling middleware."""

import pytest
from aiogram.types import Chat, Message, User

from src.bot.middlewares.error_handler import ErrorHandlingMiddleware


@pytest.mark.asyncio
async def test_error_middleware_catches_exception():
    """Test that middleware catches and logs exceptions."""

    async def failing_handler(event, data):
        raise ValueError("Test error")

    # Create mock message
    user = User(id=12345, is_bot=False, first_name="Test")
    chat = Chat(id=12345, type="private")
    message = Message(
        message_id=1, date=1234567890, chat=chat, from_user=user, text="test"
    )

    middleware = ErrorHandlingMiddleware()

    # Should not raise exception
    result = await middleware(handler=failing_handler, event=message, data={})

    assert result is None  # Middleware returns None on error


@pytest.mark.asyncio
async def test_error_middleware_passes_success():
    """Test that middleware passes through successful handlers."""

    async def success_handler(event, data):
        return "success"

    user = User(id=12345, is_bot=False, first_name="Test")
    chat = Chat(id=12345, type="private")
    message = Message(
        message_id=1, date=1234567890, chat=chat, from_user=user, text="test"
    )

    middleware = ErrorHandlingMiddleware()

    result = await middleware(handler=success_handler, event=message, data={})

    assert result == "success"
