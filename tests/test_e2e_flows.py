from __future__ import annotations

from datetime import date, timedelta

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey

from src.bot.callbacks.data import (
    BlockerCallback,
    BlockerType,
    DeepenAction,
    DeepenCallback,
    PaywallAction,
    PaywallCallback,
    QuizAction,
    QuizAnswerCallback,
    QuizResultActionCallback,
    StepAction,
    StepCallback,
    TensionCallback,
    RatingCallback,
)
from src.bot.handlers import onboarding
from src.bot.handlers.evening import cmd_evening, process_rating
from src.bot.handlers.stuck import blocker_other, cmd_stuck
from src.bot.handlers.morning import (
    cmd_morning,
    handle_deepen_choice,
    handle_tension_after,
    handle_tension_before,
)
from src.bot.handlers.onboarding import confirm_stages, process_deadline, process_goal
from src.bot.handlers.quiz import QUIZ_QUESTIONS, handle_quiz_answer, handle_quiz_result_action
from src.bot.handlers.start import cmd_start
from src.bot.handlers.steps import handle_paywall_choice, step_done
from src.bot.states import (
    AntipanicSession,
    EveningStates,
    OnboardingSprintStates,
    OnboardingStates,
    StuckStates,
    QuizStates,
)
from src.database.models import DailyLog, Goal, Stage, Step, User
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
        self.sent.append({"text": text, "markup": reply_markup, "method": "edit_text"})
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
    return FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=user_id, user_id=user_id))


@pytest.mark.asyncio
async def test_full_user_journey_end_to_end(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: /start → квиз → мини-спринт → онбординг → /morning → /evening."""
    user = DummyUser(9001)
    state = make_state(user.id)
    start_message = DummyMessage(text="/start", from_user=user)

    async def fake_micro_step(*args, **kwargs) -> str:  # type: ignore[override]
        return "Сделать супер-микрошаг"

    async def fake_steps(*args, **kwargs):  # type: ignore[override]
        return [{"title": "Углубиться на 20 минут", "difficulty": "medium", "minutes": 20}]

    async def fake_decompose(*args, **kwargs):  # type: ignore[override]
        return [
            {"title": "Скелет MVP", "days": 2},
            {"title": "Запуск для друзей", "days": 2},
        ]

    async def fake_diagnosis(*args, **kwargs):  # type: ignore[override]
        return "Твой стопор — избегание. Дадим микрошаги и ритм."

    async def noop_reminders(**kwargs):
        return None

    monkeypatch.setattr(ai_service, "generate_micro_step", fake_micro_step)
    monkeypatch.setattr(ai_service, "generate_steps", fake_steps)
    monkeypatch.setattr(ai_service, "decompose_goal", fake_decompose)
    monkeypatch.setattr(ai_service, "generate_quiz_diagnosis", fake_diagnosis)
    monkeypatch.setattr(onboarding, "setup_user_reminders", noop_reminders)

    await cmd_start(start_message, state)
    assert await state.get_state() == QuizStates.answering.state

    # Пройти весь квиз
    for idx, question in enumerate(QUIZ_QUESTIONS):
        callback = DummyCallback(message=start_message, from_user=user)
        await handle_quiz_answer(
            callback,
            QuizAnswerCallback(question=question["number"], option=0),
            state,
        )

    assert await state.get_state() == QuizStates.finished.state

    # Запустить мини-спринт
    quiz_done_cb = DummyCallback(message=start_message, from_user=user)
    await handle_quiz_result_action(
        quiz_done_cb, QuizResultActionCallback(action=QuizAction.proceed), state
    )
    assert await state.get_state() == AntipanicSession.rating_tension_before.state

    # Антипаралич: напряжение → тело → микрошаг → пейволл
    before_cb = DummyCallback(message=start_message, from_user=user)
    await handle_tension_before(before_cb, TensionCallback(value=2), state)
    sprint_data = await state.get_data()
    sprint_body_id = sprint_data["body_step_id"]

    body_cb = DummyCallback(message=start_message, from_user=user)
    await step_done(body_cb, StepCallback(action=StepAction.done, step_id=sprint_body_id), state)
    sprint_micro_id = (await state.get_data())["micro_step_id"]

    micro_cb = DummyCallback(message=start_message, from_user=user)
    await step_done(
        micro_cb, StepCallback(action=StepAction.done, step_id=sprint_micro_id), state
    )
    assert await state.get_state() == OnboardingSprintStates.paywall.state

    # Переход в онбординг цели
    paywall_cb = DummyCallback(message=start_message, from_user=user)
    await handle_paywall_choice(
        paywall_cb, PaywallCallback(action=PaywallAction.accept), state
    )
    assert await state.get_state() == OnboardingStates.waiting_for_goal.state

    goal_msg = DummyMessage(text="Запустить MVP", from_user=user)
    await process_goal(goal_msg, state)
    assert await state.get_state() == OnboardingStates.waiting_for_deadline.state

    deadline_msg = DummyMessage(text="+5 дней", from_user=user)
    await process_deadline(deadline_msg, state)
    assert await state.get_state() == OnboardingStates.confirming_stages.state

    confirm_cb = DummyCallback(message=deadline_msg, from_user=user)
    await confirm_stages(confirm_cb, state)
    assert await state.get_state() is None

    goal = await Goal.get(user__telegram_id=user.id, status="active")
    stages = await Stage.filter(goal=goal).order_by("order")
    assert [s.title for s in stages] == ["Скелет MVP", "Запуск для друзей"]

    # Утренний поток для созданной цели
    morning_msg = DummyMessage(text="/morning", from_user=user)
    await cmd_morning(morning_msg, state)
    assert await state.get_state() == AntipanicSession.rating_tension_before.state

    before_goal_cb = DummyCallback(message=morning_msg, from_user=user)
    await handle_tension_before(before_goal_cb, TensionCallback(value=4), state)
    data = await state.get_data()
    body_step_id = data["body_step_id"]

    body_done_cb = DummyCallback(message=morning_msg, from_user=user)
    await step_done(body_done_cb, StepCallback(action=StepAction.done, step_id=body_step_id), state)
    micro_step_id = (await state.get_data())["micro_step_id"]

    micro_done_cb = DummyCallback(message=morning_msg, from_user=user)
    await step_done(
        micro_done_cb, StepCallback(action=StepAction.done, step_id=micro_step_id), state
    )
    assert await state.get_state() == AntipanicSession.rating_tension_after.state

    after_cb = DummyCallback(message=morning_msg, from_user=user)
    await handle_tension_after(after_cb, TensionCallback(value=2), state)
    assert await state.get_state() == AntipanicSession.offered_deepen.state

    finish_cb = DummyCallback(message=morning_msg, from_user=user)
    await handle_deepen_choice(
        finish_cb, DeepenCallback(action=DeepenAction.finish), state
    )
    assert await state.get_state() is None

    # Вечерний итог
    evening_msg = DummyMessage(text="/evening", from_user=user)
    await cmd_evening(evening_msg, state)
    assert await state.get_state() == EveningStates.rating_day.state

    rating_cb = DummyCallback(message=evening_msg, from_user=user)
    await process_rating(rating_cb, RatingCallback(value=5), state)
    assert await state.get_state() is None

    # Проверяем данные в БД
    db_user = await User.get(telegram_id=user.id)
    today_log = await DailyLog.get(user=db_user, date=date.today())

    assert db_user.streak_days == 1
    assert db_user.xp > 0
    assert set(today_log.completed_step_ids) >= {body_step_id, micro_step_id}
    assert today_log.xp_earned >= 8  # XP за тело + микрошаги дня


@pytest.mark.asyncio
async def test_stuck_flow_microhit_with_pending_step(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stuck flow generates microhit and keeps pending step keyboard."""
    user = DummyUser(9100)
    state = make_state(user.id)

    async def fake_microhit(*args, **kwargs):
        return "Сделай разведку: открой файл и выпиши 1 пункт."

    real_user = await User.create(telegram_id=user.id)
    goal = await Goal.create(
        user=real_user,
        title="Запуск курса",
        deadline=date.today() + timedelta(days=7),
        start_date=date.today(),
        status="active",
    )
    stage = await Stage.create(
        goal=goal,
        title="Подготовка",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=3),
        status="active",
    )
    step = await Step.create(
        stage=stage,
        title="Склей структуру",
        difficulty="easy",
        estimated_minutes=10,
        xp_reward=5,
        scheduled_date=date.today(),
        status="pending",
    )
    await DailyLog.create(user=real_user, date=date.today(), assigned_step_ids=[step.id])

    monkeypatch.setattr(ai_service, "get_microhit", fake_microhit)

    msg = DummyMessage(text="/stuck", from_user=user)
    await cmd_stuck(msg, state)
    assert await state.get_state() == StuckStates.waiting_for_blocker.state

    cb = DummyCallback(message=msg, from_user=user)
    await blocker_other(cb, BlockerCallback(type=BlockerType.no_energy), state)
    assert await state.get_state() is None

    texts = [item["text"] for item in msg.sent]
    assert any("Микро-удар" in t or "Ещё идея" in t for t in texts)
    # В ответах должна быть клавиатура с шагами (reply_markup хранится рядом с текстом)
    assert any(item.get("markup") for item in msg.sent)


@pytest.mark.asyncio
async def test_morning_evening_across_two_days(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Morning + evening flow on two consecutive days keeps streak/logs separate."""
    user = DummyUser(9200)
    state = make_state(user.id)
    real_user = await User.create(telegram_id=user.id)
    goal = await Goal.create(
        user=real_user,
        title="Двухдневный тест",
        deadline=date.today() + timedelta(days=10),
        start_date=date.today(),
        status="active",
    )
    stage = await Stage.create(
        goal=goal,
        title="Этап 1",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=5),
        status="active",
    )
    await Step.create(
        stage=stage,
        title="Базовый шаг этапа",
        difficulty="medium",
        estimated_minutes=30,
        xp_reward=10,
        scheduled_date=date.today(),
        status="pending",
    )

    async def fake_micro_step(*args, **kwargs):  # type: ignore[override]
        return "Микрошаг: записать 1 идею"

    async def fake_steps(*args, **kwargs):  # type: ignore[override]
        return [{"title": "Длиннее шаг", "difficulty": "medium", "minutes": 20}]

    monkeypatch.setattr(ai_service, "generate_micro_step", fake_micro_step)
    monkeypatch.setattr(ai_service, "generate_steps", fake_steps)

    current_day = {"today": date.today()}

    class FrozenDate(date):
        @classmethod
        def today(cls):  # type: ignore[override]
            return current_day["today"]

    # Замораживаем сегодняшнюю дату во всех хендлерах/сервисах
    monkeypatch.setattr("src.bot.handlers.morning.date", FrozenDate)
    monkeypatch.setattr("src.bot.handlers.evening.date", FrozenDate)
    monkeypatch.setattr("src.bot.handlers.steps.date", FrozenDate)
    monkeypatch.setattr("src.services.session.date", FrozenDate)

    # День 1
    await cmd_morning(DummyMessage(text="/morning", from_user=user), state)
    await handle_tension_before(
        DummyCallback(message=DummyMessage(from_user=user), from_user=user),
        TensionCallback(value=3),
        state,
    )
    day1_data = await state.get_data()
    body1 = day1_data["body_step_id"]
    await step_done(
        DummyCallback(message=DummyMessage(from_user=user), from_user=user),
        StepCallback(action=StepAction.done, step_id=body1),
        state,
    )
    micro1 = (await state.get_data())["micro_step_id"]
    await step_done(
        DummyCallback(message=DummyMessage(from_user=user), from_user=user),
        StepCallback(action=StepAction.done, step_id=micro1),
        state,
    )
    await handle_tension_after(
        DummyCallback(message=DummyMessage(from_user=user), from_user=user),
        TensionCallback(value=2),
        state,
    )
    await handle_deepen_choice(
        DummyCallback(message=DummyMessage(from_user=user), from_user=user),
        DeepenCallback(action=DeepenAction.finish),
        state,
    )
    eve1 = DummyMessage(text="/evening", from_user=user)
    await cmd_evening(eve1, state)
    await process_rating(
        DummyCallback(message=eve1, from_user=user), RatingCallback(value=4), state
    )

    # День 2
    current_day["today"] = date.today() + timedelta(days=1)
    msg2 = DummyMessage(text="/morning", from_user=user)
    await cmd_morning(msg2, state)
    await handle_tension_before(
        DummyCallback(message=msg2, from_user=user), TensionCallback(value=4), state
    )
    body2 = (await state.get_data())["body_step_id"]
    await step_done(
        DummyCallback(message=msg2, from_user=user),
        StepCallback(action=StepAction.done, step_id=body2),
        state,
    )
    micro2 = (await state.get_data())["micro_step_id"]
    await step_done(
        DummyCallback(message=msg2, from_user=user),
        StepCallback(action=StepAction.done, step_id=micro2),
        state,
    )
    await handle_tension_after(
        DummyCallback(message=msg2, from_user=user),
        TensionCallback(value=1),
        state,
    )
    await handle_deepen_choice(
        DummyCallback(message=msg2, from_user=user),
        DeepenCallback(action=DeepenAction.finish),
        state,
    )
    eve2 = DummyMessage(text="/evening", from_user=user)
    await cmd_evening(eve2, state)
    await process_rating(
        DummyCallback(message=eve2, from_user=user), RatingCallback(value=5), state
    )

    db_user = await User.get(telegram_id=user.id)
    log1 = await DailyLog.get(user=db_user, date=current_day["today"] - timedelta(days=1))
    log2 = await DailyLog.get(user=db_user, date=current_day["today"])

    assert db_user.streak_days == 2
    assert log1.date != log2.date
    assert set(log1.completed_step_ids) and set(log2.completed_step_ids)
    assert log1.date < log2.date
    assert db_user.xp > 0
