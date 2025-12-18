"""
Тесты для флоу создания новой цели через /goals.

AICODE-NOTE: Проверяем:
1. Кнопка "➕ Новая цель" появляется когда < 10 активных целей
2. Callback on_create_goal правильно переключает FSM state
3. Onboarding flow продолжается после callback
"""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User as TgUser

from src.bot.callbacks.data import GoalManageAction, GoalManageCallback
from src.bot.handlers.manage_goals import cmd_goals, on_create_goal
from src.bot.handlers.onboarding import process_goal, process_deadline
from src.bot.states import OnboardingStates
from src.database.models import Goal, User


@pytest.mark.asyncio
async def test_goals_list_shows_create_button_when_under_limit(user: User):
    """
    Тест: кнопка '➕ Новая цель' появляется когда < 10 активных целей.
    """
    # Create 1 active goal
    await Goal.create(
        user=user,
        title="Existing Goal",
        start_date=date.today(),
        deadline=date.today() + timedelta(days=30),
        status="active",
    )

    # Mock message
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = user.telegram_id
    message.answer = AsyncMock()

    state = MagicMock(spec=FSMContext)

    # Call handler
    await cmd_goals(message, state)

    # Check that message contains "создай новую"
    call_args = message.answer.call_args
    assert call_args is not None
    text = call_args[0][0]
    assert "создай новую" in text.lower() or "новую" in text.lower()

    # Check that keyboard has "➕ Новая цель" button
    markup = call_args[1].get("reply_markup")
    assert markup is not None
    
    # Find button with text "➕ Новая цель"
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    create_button = next(
        (btn for btn in buttons if "Новая цель" in btn.text),
        None
    )
    assert create_button is not None, "Button '➕ Новая цель' not found"
    
    # Check callback_data is GoalManageCallback with action=create
    callback_data = create_button.callback_data
    assert "create" in callback_data


@pytest.mark.asyncio
async def test_goals_list_hides_create_button_when_at_limit(user: User):
    """
    Тест: кнопка '➕ Новая цель' НЕ появляется когда ≥ 10 активных целей.
    """
    # Create 10 active goals (limit)
    for i in range(1, 11):
        await Goal.create(
            user=user,
            title=f"Goal {i}",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=30 + i),
            status="active",
        )

    # Mock message
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = user.telegram_id
    message.answer = AsyncMock()

    state = MagicMock(spec=FSMContext)

    # Call handler
    await cmd_goals(message, state)

    # Check that keyboard does NOT have "➕ Новая цель" button
    call_args = message.answer.call_args
    markup = call_args[1].get("reply_markup")
    assert markup is not None
    
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    create_button = next(
        (btn for btn in buttons if "Новая цель" in btn.text),
        None
    )
    assert create_button is None, "Button '➕ Новая цель' should not be shown at limit"


@pytest.mark.asyncio
async def test_create_goal_callback_switches_to_onboarding_state(user: User):
    """
    Тест: callback on_create_goal переключает FSM state на OnboardingStates.waiting_for_goal.
    """
    # Mock callback
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = user.telegram_id
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    callback_data = GoalManageCallback(goal_id=0, action=GoalManageAction.create)

    state = MagicMock(spec=FSMContext)
    state.clear = AsyncMock()
    state.set_state = AsyncMock()

    # Call handler
    await on_create_goal(callback, callback_data, state)

    # Check that FSM state was switched
    state.clear.assert_called_once()
    state.set_state.assert_called_once_with(OnboardingStates.waiting_for_goal)

    # Check that message was edited with onboarding prompt
    callback.message.edit_text.assert_called_once()
    call_args = callback.message.edit_text.call_args
    text = call_args[0][0]
    assert "цель" in text.lower()
    assert "Python" in text or "блог" in text  # Example goals


@pytest.mark.asyncio
async def test_create_goal_callback_blocks_when_at_limit(user: User):
    """
    Тест: callback on_create_goal блокирует создание при достижении лимита (10 целей).
    """
    # Create 10 active goals (limit)
    for i in range(1, 11):
        await Goal.create(
            user=user,
            title=f"Goal {i}",
            start_date=date.today(),
            deadline=date.today() + timedelta(days=30 + i),
            status="active",
        )

    # Mock callback
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TgUser)
    callback.from_user.id = user.telegram_id
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    callback_data = GoalManageCallback(goal_id=0, action=GoalManageAction.create)

    state = MagicMock(spec=FSMContext)
    state.clear = AsyncMock()
    state.set_state = AsyncMock()

    # Call handler
    await on_create_goal(callback, callback_data, state)

    # Check that warning message was shown
    call_args = callback.message.edit_text.call_args
    text = call_args[0][0]
    assert "лимит" in text.lower() or "10 активных" in text.lower()

    # Check that FSM state was NOT switched
    state.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_onboarding_flow_continues_after_create_callback(user: User):
    """
    Тест: после on_create_goal можно продолжить onboarding flow (ввод цели → дедлайн).
    """
    # Mock message for goal input
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(spec=TgUser)
    message.from_user.id = user.telegram_id
    message.text = "Выучить Go"
    message.answer = AsyncMock()

    state = MagicMock(spec=FSMContext)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    # Call process_goal (onboarding step 1)
    await process_goal(message, state)

    # Check that goal text was saved to FSM
    state.update_data.assert_called_once_with(goal_text="Выучить Go")
    state.set_state.assert_called_once_with(OnboardingStates.waiting_for_deadline)

    # Check that deadline prompt was shown
    message.answer.assert_called_once()
    call_args = message.answer.call_args
    text = call_args[0][0]
    assert "дедлайн" in text.lower() or "когда" in text.lower()

