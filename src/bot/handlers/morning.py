"""
Morning handlers — antiparalysis flow.

Flow:
1) /morning → выбор цели (если несколько)
2) шкала напряжения 0–10
3) телесное микродействие 2–3 мин → кнопка «Сделал»
4) микрошаг по задаче 2–5 мин → кнопка «Сделал»
5) замер напряжения после → предложение углубиться 15–30 мин или завершить

AICODE-NOTE: Refactored in Stage 2.2 TMA migration.
Handler is now thin - uses AssignMorningStepsUseCase for business logic.
"""

import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.callbacks.data import (
    DeepenAction,
    DeepenCallback,
    GoalSelectCallback,
    TensionCallback,
)
from src.bot.keyboards import (
    deepen_keyboard,
    goal_select_keyboard,
    main_menu_keyboard,
    steps_list_keyboard,
    tension_keyboard,
)
from src.bot.states import AntipanicSession
from src.bot.utils import get_callback_message
from src.core.use_cases.assign_morning_steps import assign_morning_steps_use_case
from src.database.models import Goal, Stage, User
from src.services.session import support_message

logger = logging.getLogger(__name__)

router = Router()


async def _ask_tension(target: Message | CallbackQuery, state: FSMContext, goal: Goal):
    await state.set_state(AntipanicSession.rating_tension_before)
    text = (
        f"Фокус: *{goal.title}*\n\n"
        "Оцени текущее напряжение/заморозку от 0 до 10 "
        "(0 — спокойно, 10 — паника)."
    )
    if isinstance(target, CallbackQuery):
        msg = get_callback_message(target)
        await msg.edit_text(text, reply_markup=tension_keyboard())
    else:
        await target.answer(text, reply_markup=tension_keyboard())


async def _get_or_create_onboarding_sprint_goal(user: User) -> Goal:
    goal = await Goal.get_or_none(user=user, status="onboarding")
    if goal:
        return goal

    deadline = date.today() + timedelta(days=3)
    goal = await Goal.create(
        user=user,
        title="Мини-спринт после квиза",
        description="Временная цель для разморозки до полноценной цели",
        start_date=date.today(),
        deadline=deadline,
        status="onboarding",
    )
    await Stage.create(
        goal=goal,
        title="Мини-спринт",
        order=1,
        start_date=date.today(),
        end_date=deadline,
        status="active",
    )
    return goal


async def start_onboarding_sprint_flow(
    target: Message | CallbackQuery, state: FSMContext, user: User
) -> None:
    """Запуск мини-спринта без выбора цели (после квиза)."""
    goal = await _get_or_create_onboarding_sprint_goal(user)
    await state.clear()
    await state.update_data(onboarding_sprint=True, goal_id=goal.id)
    await _ask_tension(target=target, state=state, goal=goal)


@router.message(F.text.casefold().in_(("утро", "/morning")))
async def morning_from_menu(message: Message, state: FSMContext) -> None:
    """Запуск /morning из меню."""
    await cmd_morning(message, state)


@router.message(Command("morning"))
async def cmd_morning(message: Message, state: FSMContext) -> None:
    """Антипараличный старт: сразу в действие."""
    if not message.from_user:
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        await message.answer("Сначала напиши /start чтобы создать цель.")
        return

    stored = await state.get_data()
    onboarding_sprint = stored.get("onboarding_sprint")
    await state.clear()
    if onboarding_sprint:
        await state.update_data(onboarding_sprint=True)

    goals = await Goal.filter(user=user, status="active").order_by("id")
    if onboarding_sprint:
        goal = await _get_or_create_onboarding_sprint_goal(user)
        await state.update_data(goal_id=goal.id)
        await _ask_tension(message, state, goal)
        return

    if not goals:
        await message.answer(
            "У тебя нет активной цели.\nНапиши /start чтобы создать.",
            reply_markup=main_menu_keyboard(),
        )
        return

    if len(goals) == 1:
        goal = goals[0]
        await state.update_data(goal_id=goal.id)
        await _ask_tension(message, state, goal)
        return

    await state.set_state(AntipanicSession.selecting_topic)
    await message.answer(
        "Выбери, к какой цели подключаемся прямо сейчас:",
        reply_markup=goal_select_keyboard(goals),
    )


@router.callback_query(AntipanicSession.selecting_topic, GoalSelectCallback.filter())
async def select_goal(
    callback: CallbackQuery, callback_data: GoalSelectCallback, state: FSMContext
) -> None:
    """Выбор активной цели если их несколько."""
    msg = get_callback_message(callback)
    await callback.answer()
    if not callback.from_user:
        return

    user = await User.get_or_none(telegram_id=callback.from_user.id)
    goal = await Goal.get_or_none(id=callback_data.goal_id, user=user)
    if not goal:
        await state.clear()
        await msg.edit_text(
            "Цель не найдена. Напиши /start"
        )
        return

    await state.update_data(goal_id=goal.id)
    await _ask_tension(callback, state, goal)


@router.callback_query(AntipanicSession.rating_tension_before, TensionCallback.filter())
async def handle_tension_before(
    callback: CallbackQuery, callback_data: TensionCallback, state: FSMContext
) -> None:
    """После оценки напряжения → телесное действие."""
    msg = get_callback_message(callback)
    await callback.answer()
    if not callback.from_user:
        return

    user = await User.get_or_none(telegram_id=callback.from_user.id)
    if not user:
        await state.clear()
        await msg.edit_text("Сначала напиши /start.")
        return

    data = await state.get_data()
    goal_id = data.get("goal_id")
    goal = await Goal.get_or_none(id=goal_id, user=user)
    if not goal:
        await state.clear()
        await msg.edit_text("Цель не найдена. Напиши /start.")
        return

    tension = callback_data.value
    await state.update_data(tension_before=tension)

    # Use use-case to create body step
    result = await assign_morning_steps_use_case.create_body_step(
        user=user, goal=goal, tension=tension
    )

    if not result.success:
        await state.clear()
        await msg.edit_text(
            f"Не получилось создать шаг: {result.error_message}",
        )
        return

    body_step = result.step
    body_text = result.action_text

    if not body_step:
        await msg.edit_text("Не удалось создать шаг.")
        return

    await state.update_data(body_step_id=body_step.id)
    await state.set_state(AntipanicSession.doing_body_action)

    await msg.edit_text(
        f"🤸 Разморозка на 2 минуты для цели *{goal.title}*.\n\n"
        f"👉 {body_text}\n\n"
        "Нажми «Шаг 1» когда сделаешь или «🆘» если нужен обходной путь.",
        reply_markup=steps_list_keyboard([body_step.id]),
    )


@router.callback_query(AntipanicSession.rating_tension_after, TensionCallback.filter())
async def handle_tension_after(
    callback: CallbackQuery, callback_data: TensionCallback, state: FSMContext
) -> None:
    """Замер после действий → предложение углубиться или завершить."""
    msg = get_callback_message(callback)
    await callback.answer()
    data = await state.get_data()
    before = data.get("tension_before")
    after = callback_data.value

    support = support_message(before=before, after=after)
    await state.update_data(tension_after=after)
    await state.set_state(AntipanicSession.offered_deepen)

    await msg.edit_text(
        f"{support}\n\nГотов попробовать ещё один шаг на 15–30 минут или завершаем?",
        reply_markup=deepen_keyboard(),
    )


@router.callback_query(AntipanicSession.offered_deepen, DeepenCallback.filter())
async def handle_deepen_choice(
    callback: CallbackQuery, callback_data: DeepenCallback, state: FSMContext
) -> None:
    """Решение: пойти в мини-спринт или закончить сессию."""
    msg = get_callback_message(callback)
    await callback.answer()
    if not callback.from_user:
        return

    user = await User.get_or_none(telegram_id=callback.from_user.id)
    data = await state.get_data()
    goal_id = data.get("goal_id")
    goal = await Goal.get_or_none(id=goal_id, user=user)

    if not goal or not user:
        await state.clear()
        await msg.edit_text("Цель не найдена. Напиши /start.")
        return

    if callback_data.action == DeepenAction.finish:
        await state.clear()
        await msg.edit_text(
            "Фиксирую прогресс. Если будет ресурс — возвращайся позже 💚",
        )
        return

    # Запросить ещё один шаг на 15–30 минут через use-case
    tension_after = data.get("tension_after")
    result = await assign_morning_steps_use_case.create_task_micro_step(
        user=user, goal=goal, tension=tension_after, max_minutes=30
    )

    if not result.success:
        logger.error(f"Failed to create deepening step: {result.error_message}")
        await state.clear()
        await msg.edit_text(
            f"Не получилось подобрать следующий шаг: {result.error_message}",
        )
        return

    deep_step = result.step
    if not deep_step:
        await msg.edit_text("Не удалось создать шаг.")
        return

    await state.clear()
    await msg.edit_text(
        "🚀 Поехали чуть глубже (до 30 минут).\n\n"
        f"👉 {deep_step.title}\n\n"
        "Отметь, когда сделаешь — или напиши /evening позже для итогов.",
        reply_markup=steps_list_keyboard([deep_step.id]),
    )
