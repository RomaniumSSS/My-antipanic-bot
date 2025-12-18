"""
Тесты для /cancel команды и fallback handler.

AICODE-NOTE: Тестирование Plan 005, Phase 4 функционала.
"""

import pytest
from aiogram.types import Message, User as TgUser
from unittest.mock import AsyncMock, MagicMock

from src.bot.handlers.start import cmd_cancel
from src.bot.handlers.fallback import fallback_handler
from src.bot.states import StuckStates, OnboardingStates


@pytest.fixture
def mock_message():
    """Create a mock message."""
    message = MagicMock(spec=Message)
    message.from_user = TgUser(
        id=123456789,
        is_bot=False,
        first_name="Test",
        username="test_user",
    )
    message.answer = AsyncMock()
    message.text = None
    return message


@pytest.fixture
def mock_fsm_context():
    """Create a mock FSM context."""
    context = MagicMock()
    context.get_state = AsyncMock(return_value=None)
    context.set_state = AsyncMock()
    context.clear = AsyncMock()
    context.update_data = AsyncMock()
    context.get_data = AsyncMock(return_value={})
    return context


@pytest.mark.asyncio
async def test_cancel_clears_fsm_state(mock_message, mock_fsm_context):
    """
    Тест: /cancel очищает FSM state если пользователь в состоянии.
    """
    # Arrange: мокируем что пользователь в FSM состоянии
    mock_fsm_context.get_state.return_value = StuckStates.waiting_for_blocker.state
    
    # Act: вызываем /cancel
    await cmd_cancel(mock_message, mock_fsm_context)
    
    # Assert: state.clear() был вызван
    mock_fsm_context.clear.assert_called_once()
    
    # Assert: пользователь получил сообщение об отмене
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Отменил" in call_args or "отменил" in call_args.lower()


@pytest.mark.asyncio
async def test_cancel_when_no_state(mock_message, mock_fsm_context):
    """
    Тест: /cancel показывает сообщение если пользователь не в состоянии.
    """
    # Arrange: FSM state пустой (по умолчанию)
    mock_fsm_context.get_state.return_value = None
    
    # Act: вызываем /cancel
    await cmd_cancel(mock_message, mock_fsm_context)
    
    # Assert: state.clear() НЕ был вызван (нечего очищать)
    mock_fsm_context.clear.assert_not_called()
    
    # Assert: пользователь получил сообщение что нечего отменять
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "Нечего отменять" in call_args or "help" in call_args.lower()


@pytest.mark.asyncio
async def test_fallback_handler_with_state(mock_message, mock_fsm_context):
    """
    Тест: Fallback handler показывает подсказку про /cancel если пользователь в FSM state.
    """
    # Arrange: мокируем что пользователь в FSM состоянии
    mock_fsm_context.get_state.return_value = OnboardingStates.waiting_for_goal.state
    mock_message.text = "какой-то неожиданный текст"
    
    # Act: вызываем fallback handler
    await fallback_handler(mock_message, mock_fsm_context)
    
    # Assert: пользователь получил подсказку про /cancel
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "/cancel" in call_args or "cancel" in call_args.lower()


@pytest.mark.asyncio
async def test_fallback_handler_without_state(mock_message, mock_fsm_context):
    """
    Тест: Fallback handler показывает список команд если пользователь не в FSM state.
    """
    # Arrange: FSM state пустой
    mock_fsm_context.get_state.return_value = None
    mock_message.text = "абракадабра"
    
    # Act: вызываем fallback handler
    await fallback_handler(mock_message, mock_fsm_context)
    
    # Assert: пользователь получил список команд
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args[0][0]
    assert "/morning" in call_args or "morning" in call_args.lower()
    assert "/stuck" in call_args or "stuck" in call_args.lower()


@pytest.mark.asyncio
async def test_cancel_preserves_data_after_clear(mock_message, mock_fsm_context):
    """
    Тест: /cancel полностью очищает FSM (и state, и data).
    """
    # Arrange: мокируем что пользователь в FSM состоянии с данными
    mock_fsm_context.get_state.return_value = StuckStates.waiting_for_details.state
    mock_fsm_context.get_data.return_value = {
        "stuck_step_id": 42,
        "stuck_step_title": "Test step",
        "blocker_type": "unclear",
    }
    
    # Act: вызываем /cancel
    await cmd_cancel(mock_message, mock_fsm_context)
    
    # Assert: state.clear() был вызван (очищает и state, и data)
    mock_fsm_context.clear.assert_called_once()
    
    # Assert: пользователь получил сообщение об отмене
    mock_message.answer.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

