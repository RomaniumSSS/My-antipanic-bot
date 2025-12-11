from datetime import date, timedelta

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from src.bot.callbacks.data import (
    DeepenAction,
    DeepenCallback,
    StepAction,
    StepCallback,
    TensionCallback,
)
from src.bot.handlers import onboarding
from src.bot.handlers.evening import update_streak
from src.bot.handlers.morning import (
    cmd_morning,
    handle_deepen_choice,
    handle_tension_after,
    handle_tension_before,
)
from src.bot.handlers.onboarding import confirm_stages, process_deadline, process_goal
from src.bot.handlers.quiz import calculate_quiz_score
from src.bot.handlers.steps import step_done, step_stuck
from src.bot.states import AntipanicSession, OnboardingStates, StuckStates
from src.database.models import DailyLog, Goal, Stage, Step, User
from src.services import session as session_service
from src.services.ai import ai_service


class DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id
        self.username = "tester"
        self.first_name = "Test"


class DummyMessage:
    def __init__(self, text: str | None = None, from_user: DummyUser | None = None):
        self.text = text
        self.from_user = from_user
        self.chat = type("Chat", (), {"id": getattr(from_user, "id", None)})()
        self.sent: list[dict] = []
        self.deleted = False

    async def answer(self, text: str, reply_markup=None):
        self.sent.append({"text": text, "markup": reply_markup, "method": "answer"})
        return self

    async def edit_text(self, text: str, reply_markup=None):
        self.sent.append(
            {"text": text, "markup": reply_markup, "method": "edit_text"}
        )
        return self

    async def delete(self):
        self.deleted = True


class DummyCallback:
    def __init__(self, message: DummyMessage, from_user: DummyUser):
        self.message = message
        self.from_user = from_user
        self.answered = False

    async def answer(self, *args, **kwargs):
        self.answered = True


def make_state(user_id: int) -> FSMContext:
    storage = MemoryStorage()
    return FSMContext(
        storage=storage,
        key=StorageKey(bot_id=1, chat_id=user_id, user_id=user_id),
    )


def test_calculate_quiz_score() -> None:
    """Score is scaled to 0-100 and diff is clamped at 0."""
    answers = [{"weight": 32}]
    score, diff = calculate_quiz_score(answers)
    assert score == 100
    assert diff == 65

    answers = [{"weight": 0}]
    score, diff = calculate_quiz_score(answers)
    assert score == 0
    assert diff == 0


@pytest.mark.asyncio
async def test_update_streak(db: None) -> None:
    """Streak increments day-to-day and resets after a gap."""
    user = await User.create(telegram_id=10, streak_days=2, streak_last_date=date.today() - timedelta(days=1))

    update_streak(user, date.today())
    assert user.streak_days == 3
    assert user.streak_last_date == date.today()

    update_streak(user, date.today() + timedelta(days=2))
    assert user.streak_days == 1
    assert user.streak_last_date == date.today() + timedelta(days=2)


@pytest.mark.asyncio
async def test_session_creates_body_and_micro_steps(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Antipanic session creates steps, logs them and keeps DailyLog consistent."""
    user = await User.create(telegram_id=99)
    goal = await Goal.create(
        user=user,
        title="Test goal",
        deadline=date.today() + timedelta(days=5),
        start_date=date.today(),
        status="active",
    )
    await Stage.create(
        goal=goal,
        title="Stage",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status="active",
    )

    async def fake_micro_step(*args, **kwargs) -> str:  # type: ignore[override]
        return "Сделать дыхательную разминку"

    monkeypatch.setattr(session_service.ai_service, "generate_micro_step", fake_micro_step)

    body_step = await session_service.create_body_step(
        user=user, goal=goal, action_text="Встряхнуться", tension=4
    )
    micro_step = await session_service.get_task_micro_action(
        user=user, goal=goal, tension=4, max_minutes=5
    )

    daily_log = await DailyLog.get(user=user, date=date.today())
    assert body_step.id in daily_log.assigned_step_ids
    assert micro_step.id in daily_log.assigned_step_ids
    assert daily_log.energy_level == session_service._energy_from_tension(4)

    # Mark micro step completed and ensure log updates XP
    micro_step.status = "completed"
    micro_step.completed_at = date.today()
    await micro_step.save()
    daily_log.completed_step_ids.append(micro_step.id)
    daily_log.xp_earned = (daily_log.xp_earned or 0) + micro_step.xp_reward
    await daily_log.save()

    updated_log = await DailyLog.get(user=user, date=date.today())
    assert micro_step.id in updated_log.completed_step_ids
    assert updated_log.xp_earned >= micro_step.xp_reward


@pytest.mark.asyncio
async def test_onboarding_flow_creates_goal_and_stages(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy-path onboarding flow wires states, callbacks and DB writes."""
    tg_id = 5011
    await User.create(telegram_id=tg_id)
    state = make_state(tg_id)
    await state.set_state(OnboardingStates.waiting_for_goal)

    user_stub = DummyUser(tg_id)
    msg_goal = DummyMessage(text="Запустить курс", from_user=user_stub)
    await process_goal(msg_goal, state)

    assert await state.get_state() == OnboardingStates.waiting_for_deadline.state
    assert (await state.get_data())["goal_text"] == "Запустить курс"

    async def fake_decompose(*args, **kwargs):
        return [{"title": "Первый", "days": 2}, {"title": "Второй", "days": 1}]

    monkeypatch.setattr(ai_service, "decompose_goal", fake_decompose)
    reminders: list[dict] = []

    async def fake_reminders(**kwargs):
        reminders.append(kwargs)

    monkeypatch.setattr(onboarding, "setup_user_reminders", fake_reminders)

    msg_deadline = DummyMessage(text="+3 дня", from_user=user_stub)
    await process_deadline(msg_deadline, state)

    assert await state.get_state() == OnboardingStates.confirming_stages.state
    confirm_markup = msg_deadline.sent[-1]["markup"]
    first_cb = confirm_markup.inline_keyboard[0][0].callback_data
    assert isinstance(first_cb, str) and first_cb.startswith("confirm:")

    callback = DummyCallback(message=msg_deadline, from_user=user_stub)
    await confirm_stages(callback, state)

    assert await state.get_state() is None
    goal = await Goal.get(user__telegram_id=tg_id)
    stages = await Stage.filter(goal=goal).order_by("order")

    assert goal.title == "Запустить курс"
    assert [s.title for s in stages] == ["Первый", "Второй"]
    assert stages[0].status == "active"
    assert reminders


@pytest.mark.asyncio
async def test_morning_antipanic_flow_callbacks_chain(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FSM transitions through morning → body → micro → rating flow."""
    tg_id = 6022
    user = await User.create(telegram_id=tg_id)
    goal = await Goal.create(
        user=user,
        title="Цель дня",
        deadline=date.today() + timedelta(days=5),
        start_date=date.today(),
        status="active",
    )
    await Stage.create(
        goal=goal,
        title="Этап",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status="active",
    )
    await Step.create(
        stage=await Stage.get(goal=goal),
        title="Запасной",
        difficulty="easy",
        estimated_minutes=10,
        xp_reward=5,
        scheduled_date=date.today(),
        status="pending",
    )

    state = make_state(tg_id)
    msg = DummyMessage(text="/morning", from_user=DummyUser(tg_id))

    await cmd_morning(msg, state)
    assert await state.get_state() == AntipanicSession.rating_tension_before.state
    assert (await state.get_data())["goal_id"] == goal.id

    async def fake_micro_step(**kwargs):
        return "Сделать короткий шаг"

    async def fake_steps(**kwargs):
        return [{"title": "Длинный шаг", "minutes": 10, "difficulty": "medium"}]

    monkeypatch.setattr(session_service.ai_service, "generate_micro_step", fake_micro_step)
    monkeypatch.setattr(session_service.ai_service, "generate_steps", fake_steps)

    cb_before = DummyCallback(message=msg, from_user=msg.from_user)
    await handle_tension_before(cb_before, TensionCallback(value=2), state)
    assert await state.get_state() == AntipanicSession.doing_body_action.state
    body_step_id = (await state.get_data())["body_step_id"]
    assert await Step.filter(id=body_step_id).exists()

    body_done = DummyCallback(message=msg, from_user=msg.from_user)
    await step_done(
        body_done,
        StepCallback(action=StepAction.done, step_id=body_step_id),
        state,
    )
    assert await state.get_state() == AntipanicSession.doing_micro_action.state
    micro_step_id = (await state.get_data())["micro_step_id"]
    assert await Step.filter(id=micro_step_id).exists()

    micro_done = DummyCallback(message=msg, from_user=msg.from_user)
    await step_done(
        micro_done,
        StepCallback(action=StepAction.done, step_id=micro_step_id),
        state,
    )
    assert await state.get_state() == AntipanicSession.rating_tension_after.state
    tension_markup = msg.sent[-1]["markup"]
    assert tension_markup.inline_keyboard[0][0].callback_data.startswith("tension:")

    after_cb = DummyCallback(message=msg, from_user=msg.from_user)
    await handle_tension_after(after_cb, TensionCallback(value=1), state)
    assert await state.get_state() == AntipanicSession.offered_deepen.state

    finish_cb = DummyCallback(message=msg, from_user=msg.from_user)
    await handle_deepen_choice(
        finish_cb, DeepenCallback(action=DeepenAction.finish), state
    )
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_step_stuck_moves_into_stuck_flow(db: None) -> None:
    """Step callback 'stuck' rewires FSM to stuck flow with blocker keyboard."""
    tg_id = 7033
    user = await User.create(telegram_id=tg_id)
    goal = await Goal.create(
        user=user,
        title="Цель",
        deadline=date.today() + timedelta(days=4),
        start_date=date.today(),
        status="active",
    )
    stage = await Stage.create(
        goal=goal,
        title="Этап",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1),
        status="active",
    )
    step = await Step.create(
        stage=stage,
        title="Шаг",
        difficulty="easy",
        estimated_minutes=5,
        xp_reward=3,
        scheduled_date=date.today(),
        status="pending",
    )

    state = make_state(tg_id)
    msg = DummyMessage(from_user=DummyUser(tg_id))
    cb = DummyCallback(message=msg, from_user=msg.from_user)

    await step_stuck(
        cb, StepCallback(action=StepAction.stuck, step_id=step.id), state
    )

    assert await state.get_state() == StuckStates.waiting_for_blocker.state
    assert (await state.get_data())["stuck_step_id"] == step.id
    blocker_markup = msg.sent[-1]["markup"]
    assert blocker_markup.inline_keyboard[0][0].callback_data.startswith("blocker:")
