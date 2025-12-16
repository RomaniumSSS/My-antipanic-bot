"""
Stuck handlers — помощь при застревании.

Flow:
1. /stuck или кнопка "Застрял" — быстрый доступ к помощи
2. Выбор типа блокера (опционально)
3. AI генерирует НЕСКОЛЬКО вариантов микро-ударов на выбор (Stage 2.3)
4. Пользователь выбирает подходящий вариант
5. Показывается выбранный вариант с кнопками "Делаю" / "Ещё варианты" / "Другое"

AICODE-NOTE: Refactored in Stage 2.3 TMA migration.
Handler is now thin - uses ResolveStuckUseCase for business logic.
"""

import logging

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.callbacks.data import (
    BlockerCallback,
    BlockerType,
    MicrohitFeedbackAction,
    MicrohitFeedbackCallback,
    MicrohitOptionCallback,
)
from src.bot.keyboards import (
    blocker_keyboard,
    main_menu_keyboard,
    microhit_feedback_keyboard,
    microhit_options_keyboard,
)
from src.bot.states import StuckStates
from src.core.domain.stuck_rules import get_blocker_emoji
from src.core.use_cases.resolve_stuck import resolve_stuck_use_case
from src.database.models import DailyLog, Goal, Step, User
from src.storage import daily_log_repo

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text.casefold().in_(("застрял", "/stuck")))
async def stuck_from_menu(message: Message, state: FSMContext) -> None:
    """Поддержка кнопки меню для /stuck."""
    await cmd_stuck(message, state)


@router.message(Command("stuck"))
async def cmd_stuck(message: Message, state: FSMContext) -> None:
    """
    Быстрый вход при ступоре — без привязки к конкретному шагу.
    Сразу предлагает выбрать тип блокера и получить микро-удар.
    """
    if not message.from_user:
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        await message.answer("Напиши /start чтобы начать.")
        return

    active_goal = await Goal.filter(user=user, status="active").first()
    if not active_goal:
        await message.answer(
            "У тебя нет активной цели. Напиши /start",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Use use-case to get stuck context
    context_result = await resolve_stuck_use_case.get_stuck_context(user, active_goal)

    if not context_result.success:
        await message.answer(
            f"Не получилось определить контекст: {context_result.error_message}",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.update_data(
        stuck_step_id=context_result.step_id,
        stuck_step_title=context_result.step_title,
        stuck_goal_id=active_goal.id,
    )
    await state.set_state(StuckStates.waiting_for_blocker)

    await message.answer(
        "🆘 *Что мешает двигаться?*",
        reply_markup=blocker_keyboard(),
    )


@router.callback_query(
    StuckStates.waiting_for_blocker,
    BlockerCallback.filter(F.type == BlockerType.unclear),
)
async def blocker_unclear(callback: CallbackQuery, state: FSMContext) -> None:
    """Блокер "не знаю с чего начать" — запрашиваем детали."""
    await callback.answer()

    await state.update_data(blocker_type=BlockerType.unclear.value)
    await state.set_state(StuckStates.waiting_for_details)

    data = await state.get_data()
    step_title = data.get("stuck_step_title", "задача")

    await callback.message.edit_text(
        f"Понял, не знаешь с чего начать *{step_title}*.\n\n"
        "Расскажи подробнее — что именно непонятно?\n"
        "Или напиши `-` если не хочешь уточнять."
    )


@router.callback_query(StuckStates.waiting_for_blocker, BlockerCallback.filter())
async def blocker_other(
    callback: CallbackQuery, callback_data: BlockerCallback, state: FSMContext
) -> None:
    """Обработка других типов блокеров — сразу к вариантам микро-ударов."""
    await callback.answer()

    blocker_type = callback_data.type
    await state.update_data(blocker_type=blocker_type.value)

    # Get user for adaptive tone (plan 004)
    user = None
    if callback.from_user:
        user = await User.get_or_none(telegram_id=callback.from_user.id)

    # Generate multiple microhit options (can edit since it's bot message)
    await generate_and_show_microhit_options(
        callback.message, state, details="", can_edit=True, user=user
    )


@router.message(StuckStates.waiting_for_details)
async def process_details(message: Message, state: FSMContext) -> None:
    """Получение деталей и генерация микро-ударов (несколько вариантов)."""
    details = message.text or ""
    if details == "-":
        details = ""

    # Get user for adaptive tone (plan 004)
    user = None
    if message.from_user:
        user = await User.get_or_none(telegram_id=message.from_user.id)

    await generate_and_show_microhit_options(message, state, details, user=user)


async def generate_and_show_microhit_options(
    message_or_callback_msg,
    state: FSMContext,
    details: str,
    *,
    can_edit: bool = False,
    user: User | None = None,
) -> None:
    """
    Генерация и показ НЕСКОЛЬКИХ вариантов микро-ударов (Stage 2.3).

    Key improvement: instead of showing one microhit and waiting for "more" request,
    we generate 2-3 options upfront for user to choose from.

    Plan 004: передаём user/daily_log для адаптивного тона.
    """
    data = await state.get_data()
    step_title = data.get("stuck_step_title", "задача")
    blocker_type = data.get("blocker_type", "unclear")
    step_id = data.get("stuck_step_id")

    # Get user and daily_log for adaptive tone (plan 004)
    daily_log: DailyLog | None = None
    if user:
        from datetime import date

        daily_log = await daily_log_repo.get_or_create_daily_log(user, date.today())

    # Show loading indicator
    if can_edit:
        wait_msg = await message_or_callback_msg.edit_text(
            "🤔 Думаю над вариантами микро-ударов..."
        )
    else:
        wait_msg = await message_or_callback_msg.answer(
            "🤔 Думаю над вариантами микро-ударов..."
        )

    # Use use-case to generate multiple options with adaptive tone (plan 004)
    result = await resolve_stuck_use_case.generate_microhit_options(
        step_title=step_title,
        blocker_type=blocker_type,
        details=details,
        user=user,
        daily_log=daily_log,
    )

    if not result.success:
        await state.clear()
        error_text = (
            f"Не получилось сгенерировать варианты: {result.error_message}\n\n"
            "Попробуй ещё раз или напиши /morning"
        )
        if hasattr(wait_msg, "edit_text"):
            await wait_msg.edit_text(error_text)
        else:
            await message_or_callback_msg.answer(error_text)
        return

    options = result.options
    blocker_key = (
        BlockerType(blocker_type)
        if blocker_type in [b.value for b in BlockerType]
        else BlockerType.unclear
    )
    blocker_emoji = get_blocker_emoji(blocker_type)

    # Build message with all options listed (plan 004: подчеркиваем автономию выбора)
    options_text = "\n\n".join(
        [f"{i}️⃣ {opt.text}" for i, opt in enumerate(options, start=1)]
    )

    result_text = (
        f"🎯 *Выбери вариант который тебе ближе:*\n\n"
        f"{options_text}\n\n"
        f"💡 Выбирай любой — главное начать. Всего 2-5 минут."
    )

    # Save options to state for later reference
    await state.update_data(
        microhit_options=[opt.text for opt in options],
        blocker_type=blocker_type,
        stuck_step_id=step_id,
    )
    await state.set_state(
        StuckStates.waiting_for_blocker
    )  # Reuse state for option selection

    # Show options keyboard
    options_markup = microhit_options_keyboard(options, blocker_key, step_id)

    if hasattr(wait_msg, "edit_text"):
        await wait_msg.edit_text(result_text, reply_markup=options_markup)
    else:
        await message_or_callback_msg.answer(result_text, reply_markup=options_markup)

    logger.info(
        f"Generated {len(options)} microhit options for step='{step_title}' blocker='{blocker_type}'"
    )


@router.callback_query(MicrohitOptionCallback.filter())
async def microhit_option_selected(
    callback: CallbackQuery, callback_data: MicrohitOptionCallback, state: FSMContext
) -> None:
    """
    Handler for microhit option selection (Stage 2.3).

    User clicked one of the option buttons → show that option with action buttons.
    """
    await callback.answer()

    index = callback_data.index
    blocker = callback_data.blocker
    step_id = callback_data.step_id or None

    # Get options from state
    data = await state.get_data()
    options = data.get("microhit_options", [])

    if index < 1 or index > len(options):
        await callback.message.edit_text(
            "Не нашёл этот вариант. Попробуй ещё раз или напиши /morning"
        )
        return

    selected_text = options[index - 1]
    blocker_emoji = get_blocker_emoji(blocker.value)

    # Show selected microhit with action buttons
    result_text = (
        f"{blocker_emoji} *Выбранный микро-удар:*\n\n"
        f"{selected_text}\n\n"
        f"💡 Попробуй это прямо сейчас — всего 2-5 минут!"
    )

    feedback_markup = microhit_feedback_keyboard(step_id, blocker)

    await callback.message.edit_text(result_text, reply_markup=feedback_markup)
    await state.clear()

    logger.info(f"User selected microhit option {index} for blocker='{blocker.value}'")


@router.callback_query(MicrohitFeedbackCallback.filter())
async def microhit_feedback(
    callback: CallbackQuery, callback_data: MicrohitFeedbackCallback, state: FSMContext
) -> None:
    """Обработка реакции на микро-удар."""
    await callback.answer()

    action = callback_data.action
    step_id = callback_data.step_id or None  # 0 → None
    blocker = callback_data.blocker

    if action == MicrohitFeedbackAction.do:
        await callback.message.edit_text(
            "🔥 Отлично! Действуй. Напиши, если нужна будет ещё подсказка."
        )
        await callback.message.answer(
            "Когда сделаешь — отмечай в /status или жми /morning"
        )
        await callback.message.answer(
            "Главное меню:", reply_markup=main_menu_keyboard()
        )
        return

    if action == MicrohitFeedbackAction.other:
        # Сохраняем контекст и ждём уточнения текстом
        step_title = "задача"
        if step_id:
            step = await Step.get_or_none(id=step_id)
            if step:
                step_title = step.title

        await state.update_data(
            feedback_step_id=step_id,
            feedback_step_title=step_title,
            feedback_blocker=blocker.value,
        )
        await state.set_state(StuckStates.waiting_for_feedback_details)

        await callback.message.edit_text(
            "Ок, напиши, что именно хочешь уточнить — попробую помочь."
        )
        return

    if action == MicrohitFeedbackAction.more:
        # Generate NEW set of microhit options (Stage 2.3)
        if not callback.from_user:
            return
        user = await User.get_or_none(telegram_id=callback.from_user.id)
        if not user:
            await callback.message.edit_text("Не нашёл профиль. Напиши /start.")
            return

        # Get active goal for context
        active_goal = await Goal.filter(user=user, status="active").first()
        if not active_goal:
            await callback.message.edit_text("Не нашёл активную цель. Напиши /start.")
            return

        # Get step title
        step_title = "задача"
        if step_id:
            step = await Step.get_or_none(id=step_id)
            if step:
                step_title = step.title
        else:
            # Use context from goal
            context_result = await resolve_stuck_use_case.get_stuck_context(
                user, active_goal
            )
            if context_result.success:
                step_title = context_result.step_title
                step_id = context_result.step_id

        # Generate new set of options (plan 004: pass user for adaptive tone)
        await state.update_data(
            stuck_step_title=step_title,
            stuck_step_id=step_id,
            blocker_type=blocker.value,
        )

        await generate_and_show_microhit_options(
            callback.message, state, details="", can_edit=True, user=user
        )


@router.message(StuckStates.waiting_for_feedback_details)
async def microhit_feedback_details(message: Message, state: FSMContext) -> None:
    """Детали после кнопки 'Другое' → новый микро-удар."""
    await _process_microhit_feedback_details(message, state)


@router.message(StuckStates.waiting_for_blocker)
async def stuck_free_text_fallback(message: Message, state: FSMContext) -> None:
    """Показываем меню, если прислали текст вместо выбора блокера."""
    await message.answer(
        "Если нужна помощь — выбери кнопку или вернись в меню.",
        reply_markup=main_menu_keyboard(),
    )


@router.message()
async def microhit_feedback_details_fallback(
    message: Message, state: FSMContext
) -> None:
    """
    Fallback: если по какой-то причине состояние потерялось,
    но в данных FSM остался контекст feedback_* — продолжаем диалог,
    чтобы пользователь не зависал без ответа.
    """
    text = (message.text or "").strip().lower()
    # Пропускаем стандартные команды, чтобы не блокировать вечер/утро/старт,
    # даже если висит контекст stuck-диалога.
    if text.startswith("/"):
        raise SkipHandler()
    if text in {"вечер", "evening", "утро", "morning", "старт", "/start", "start"}:
        raise SkipHandler()

    data = await state.get_data()
    has_feedback_context = data.get("feedback_blocker")
    current_state = await state.get_state()
    stuck_states = {
        StuckStates.waiting_for_blocker.state,
        StuckStates.waiting_for_details.state,
        StuckStates.waiting_for_feedback_details.state,
    }

    if has_feedback_context:
        if current_state != StuckStates.waiting_for_feedback_details.state:
            # Восстанавливаем ожидаемое состояние и продолжаем обработку
            await state.set_state(StuckStates.waiting_for_feedback_details)
        await _process_microhit_feedback_details(message, state)
        return

    if current_state in stuck_states:
        await message.answer(
            "Я всё ещё жду, что мешает двигаться. Выбери блокер кнопкой "
            "или вернись в меню.",
            reply_markup=main_menu_keyboard(),
        )
        return

    raise SkipHandler()  # Пропускаем к следующим хендлерам


async def _process_microhit_feedback_details(
    message: Message, state: FSMContext
) -> None:
    """
    Обработка уточняющих деталей для микро-удара (Stage 2.3).

    Generates multiple microhit options based on user details.
    """
    details = message.text or ""
    data = await state.get_data()

    step_id = data.get("feedback_step_id")
    step_title = data.get("feedback_step_title", "задача")
    blocker_value = data.get("feedback_blocker", BlockerType.unclear.value)

    if step_id and step_title == "задача":
        step = await Step.get_or_none(id=step_id)
        if step:
            step_title = step.title

    try:
        blocker = BlockerType(blocker_value)
    except Exception as err:
        logger.exception("Failed to restore blocker from state: %s", err)
        await state.clear()
        await message.answer(
            "Не разобрался, какой блокер обсуждаем. Нажми /morning или /status, "
            "если нужна помощь с шагами."
        )
        return

    # Update state with context and generate options
    await state.update_data(
        stuck_step_title=step_title,
        stuck_step_id=step_id,
        blocker_type=blocker.value,
    )

    # Get user for adaptive tone (plan 004)
    user = None
    if message.from_user:
        user = await User.get_or_none(telegram_id=message.from_user.id)

    await generate_and_show_microhit_options(message, state, details=details, user=user)
