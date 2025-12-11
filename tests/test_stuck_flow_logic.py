from datetime import date, timedelta

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from src.bot.callbacks.data import (
    BlockerCallback,
    BlockerType,
    MicrohitFeedbackAction,
    MicrohitFeedbackCallback,
    StepAction,
    StepCallback,
)
from src.bot.handlers.steps import step_stuck
from src.bot.handlers.stuck import blocker_other, microhit_feedback
from src.bot.states import StuckStates
from src.database.models import Goal, Stage, Step, User
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

    async def answer(self, text: str, reply_markup=None):
        self.sent.append({"text": text, "markup": reply_markup, "method": "answer"})
        return self

    async def edit_text(self, text: str, reply_markup=None):
        self.sent.append({"text": text, "markup": reply_markup, "method": "edit_text"})
        return self


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


async def _create_step_for_user(user_id: int) -> tuple[User, Step]:
    user = await User.create(telegram_id=user_id)
    goal = await Goal.create(
        user=user,
        title="Цель",
        deadline=date.today() + timedelta(days=5),
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
    return user, step


@pytest.mark.asyncio
async def test_step_marked_stuck_enters_stuck_flow_once(db: None) -> None:
    """Первый вызов callback 'stuck' заводит FSM в stuck flow."""
    user, step = await _create_step_for_user(11001)
    state = make_state(user.telegram_id)
    msg = DummyMessage(from_user=DummyUser(user.telegram_id))
    cb = DummyCallback(message=msg, from_user=msg.from_user)

    await step_stuck(cb, StepCallback(action=StepAction.stuck, step_id=step.id), state)

    assert await state.get_state() == StuckStates.waiting_for_blocker.state
    data = await state.get_data()
    assert data["stuck_step_id"] == step.id
    assert data["stuck_step_title"] == step.title
    assert msg.sent[-1]["markup"] is not None
    assert step.title in msg.sent[-1]["text"]


@pytest.mark.asyncio
async def test_repeated_stuck_on_same_step_does_not_duplicate_flow(db: None) -> None:
    """Повторный stuck по тому же шагу оставляет состояние и контекст как есть."""
    user, step = await _create_step_for_user(11002)
    state = make_state(user.telegram_id)
    msg = DummyMessage(from_user=DummyUser(user.telegram_id))

    await step_stuck(
        DummyCallback(message=msg, from_user=msg.from_user),
        StepCallback(action=StepAction.stuck, step_id=step.id),
        state,
    )
    first_data = await state.get_data()

    await step_stuck(
        DummyCallback(message=msg, from_user=msg.from_user),
        StepCallback(action=StepAction.stuck, step_id=step.id),
        state,
    )
    second_data = await state.get_data()

    assert await state.get_state() == StuckStates.waiting_for_blocker.state
    assert first_data == second_data == {
        "stuck_step_id": step.id,
        "stuck_step_title": step.title,
    }
    assert len(msg.sent) == 2  # два edit_text вместо накопления новых шагов/состояний


@pytest.mark.asyncio
async def test_resolved_stuck_step_returns_to_regular_flow(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """После генерации микро-удара FSM очищается и можно продолжать работу."""
    user, step = await _create_step_for_user(11003)
    state = make_state(user.telegram_id)
    msg = DummyMessage(from_user=DummyUser(user.telegram_id))

    await step_stuck(
        DummyCallback(message=msg, from_user=msg.from_user),
        StepCallback(action=StepAction.stuck, step_id=step.id),
        state,
    )

    async def fake_microhit(*args, **kwargs):
        return "Сделай один маленький шаг."

    monkeypatch.setattr(ai_service, "get_microhit", fake_microhit)

    await blocker_other(
        DummyCallback(message=msg, from_user=msg.from_user),
        BlockerCallback(type=BlockerType.no_energy),
        state,
    )

    assert await state.get_state() is None
    assert await state.get_data() == {}
    assert any("Микро-удар" in item["text"] for item in msg.sent)

    # Нажимаем "Сделаю" после микро-удара — состояние остаётся пустым
    await microhit_feedback(
        DummyCallback(message=msg, from_user=msg.from_user),
        MicrohitFeedbackCallback(
            action=MicrohitFeedbackAction.do,
            step_id=step.id,
            blocker=BlockerType.no_energy,
        ),
        state,
    )
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_stuck_flow_on_missing_step_uses_fallback(db: None) -> None:
    """Если шаг не найден, бот отвечает fallback'ом и не меняет состояние."""
    user = await User.create(telegram_id=11004)
    state = make_state(user.telegram_id)
    msg = DummyMessage(from_user=DummyUser(user.telegram_id))

    await step_stuck(
        DummyCallback(message=msg, from_user=msg.from_user),
        StepCallback(action=StepAction.stuck, step_id=999999),
        state,
    )

    assert await state.get_state() is None
    assert await state.get_data() == {}
    assert msg.sent[-1]["text"] == "Шаг не найден."

