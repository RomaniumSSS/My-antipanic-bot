"""
Steps handlers — действия с шагами.

Callback actions:
- done: отметка выполнения
- skip: пропуск с причиной
- stuck: переход в stuck flow

AICODE-NOTE: Handler теперь тонкий - бизнес-логика вынесена в use-cases.
Handler только:
- Принимает ввод от пользователя
- Вызывает use-case
- Показывает результат (клавиатуры, сообщения)
- Управляет FSM состояниями
"""

import logging
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.callbacks.data import (
    PaywallAction,
    PaywallCallback,
    StepAction,
    StepCallback,
)
from src.bot.keyboards import (
    main_menu_keyboard,
    paywall_keyboard,
    steps_list_keyboard,
    tension_keyboard,
)
from src.bot.states import (
    AntipanicSession,
    EveningStates,
    OnboardingSprintStates,
    OnboardingStates,
    StuckStates,
)
from src.bot.utils import escape_markdown, get_callback_message
from src.core.use_cases.complete_step import CompleteStepUseCase
from src.core.use_cases.skip_step import SkipStepUseCase
from src.database.models import DailyLog, Goal, Step, User
from src.services import session as session_service
from src.storage import user_repo

logger = logging.getLogger(__name__)

# Инициализация use-cases
complete_step_use_case = CompleteStepUseCase()
skip_step_use_case = SkipStepUseCase()

PAYWALL_TEXT = (
    "🔥 Смотри, что только что произошло:\n"
    "- Ты был в тумане и всё равно сдвинулся\n"
    '- Твой мозг получил сигнал: "я ещё могу действовать"\n'
    '- Это уже больше, чем весь "завтра начну"\n\n'
    "Чтобы это не было разовым всплеском, я предлагаю **3-дневную миссию**.\n"
    "Я буду вести тебя каждый день — микрошаги, антипаралич.\n"
    "Просто чтобы ты вышел из ступора в стабильность.\n\n"
    "**Бесплатно на 3 дня.** Дальше — $5/месяц.\n"
    "Попробуешь?"
)


router = Router()


@router.callback_query(StepCallback.filter(F.action == StepAction.done))
async def step_done(
    callback: CallbackQuery, callback_data: StepCallback, state: FSMContext
) -> None:
    """
    Отметка шага как выполненного.

    AICODE-NOTE: Thin handler - вызывает use-case и показывает результат.
    """
    msg = get_callback_message(callback)
    await callback.answer("✅ Отлично!")

    if not callback.from_user:
        return

    step_id = callback_data.step_id

    # 1. Получить пользователя
    user = await user_repo.get_user(callback.from_user.id)
    if not user:
        await msg.edit_text("Пользователь не найден.")
        return

    # 2. Вызвать use-case для выполнения шага
    result = await complete_step_use_case.execute(step_id, user)

    if not result.success:
        await msg.edit_text(f"Ошибка: {result.error_message}")
        return

    # 3. Проверяем, вызвано ли из evening flow или antipanic
    current_state = await state.get_state()
    from_evening = current_state == EveningStates.marking_done
    is_antipanic_body = current_state == AntipanicSession.doing_body_action
    is_antipanic_micro = current_state == AntipanicSession.doing_micro_action

    # 4. Обновляем сообщение и показываем результат
    today = date.today()
    daily_log = await DailyLog.get_or_none(user=user, date=today)
    assigned_ids = daily_log.assigned_step_ids if daily_log else []

    if assigned_ids:
        steps = await Step.filter(id__in=assigned_ids)
        steps_text = "\n".join(
            f"{'✅' if s.status == 'completed' else '⬜'} {escape_markdown(s.title)}" for s in steps
        )

        all_done = all(s.status == "completed" for s in steps)
        pending_steps = [s for s in steps if s.status == "pending"]

        if all_done:
            # Все шаги выполнены
            if from_evening:
                # Из evening flow - переходим к оценке дня
                await state.set_state(EveningStates.marking_done)
                from src.bot.keyboards import rating_keyboard

                await msg.edit_text(
                    f"🎉 *Все шаги отмечены!*\n\n{steps_text}\n\n"
                    f"Сделал всё. +{result.xp_earned} XP (всего: {result.total_xp}). "
                    f"Зачёт. Как прошёл день?",
                    reply_markup=rating_keyboard(),
                )
            else:
                # Обычный flow
                await msg.edit_text(
                    f"🎉 *Все шаги выполнены!*\n\n{steps_text}\n\n"
                    f"Готово. +{result.xp_earned} XP (всего: {result.total_xp}). "
                    f"Streak: {user.streak_days} дней — продолжай. "
                    f"Вечером напиши /evening для итогов."
                )
        else:
            # Есть ещё невыполненные шаги
            # Если из evening flow и больше нет pending - переходим к оценке
            if from_evening and not pending_steps:
                await state.set_state(EveningStates.marking_done)
                from src.bot.keyboards import rating_keyboard

                completed_steps = [s for s in steps if s.status == "completed"]
                xp_earned = (daily_log.xp_earned or 0) if daily_log else 0

                await msg.edit_text(
                    f"🌙 *Итоги дня*\n\n"
                    f"{steps_text}\n"
                    f"📊 Выполнено: {len(completed_steps)}/{len(steps)}\n"
                    f"⭐ +{xp_earned} XP за день. "
                    f"Двигаешься к цели.\n\n"
                    "Как прошёл день?",
                    reply_markup=rating_keyboard(),
                )
            else:
                # Показываем обновлённый список с кнопками только для pending шагов
                # AICODE-NOTE: Позитивный feedback после completion (CLAUDE_RULES.md § 2)
                if pending_steps:
                    pending_ids = [s.id for s in pending_steps]
                    await msg.edit_text(
                        f"*Шаги на сегодня:*\n{steps_text}\n\n"
                        f"Сделал. +{result.xp_earned} XP. Двигаешься к цели.",
                        reply_markup=steps_list_keyboard(pending_ids),
                    )
                else:
                    # Все pending отмечены, но не из evening flow
                    await msg.edit_text(
                        f"*Шаги на сегодня:*\n{steps_text}\n\n"
                        f"Сделал. +{result.xp_earned} XP (всего: {result.total_xp}). "
                        f"Streak: {user.streak_days} дней. Продолжай."
                    )

    if is_antipanic_body or is_antipanic_micro:
        data = await state.get_data()
        goal_id = data.get("goal_id")
        goal = await Goal.get_or_none(id=goal_id, user=user) if goal_id else None

        if is_antipanic_body and step_id == data.get("body_step_id"):
            if goal:
                try:
                    micro_step = await session_service.get_task_micro_action(
                        user=user,
                        goal=goal,
                        tension=data.get("tension_before"),
                        max_minutes=5,
                    )
                    await state.update_data(micro_step_id=micro_step.id)
                    await state.set_state(AntipanicSession.doing_micro_action)
                    await msg.answer(
                        "🔥 Тело включили, теперь микрошаг по задаче (2–5 минут):\n"
                        f"👉 {escape_markdown(micro_step.title)}",
                        reply_markup=steps_list_keyboard([micro_step.id]),
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Failed to create micro action: {e}")
            else:
                await msg.answer(
                    "Шаг сохранил. Обнови цель через /start, чтобы продолжить."
                )
        elif is_antipanic_micro and step_id == data.get("micro_step_id"):
            if data.get("onboarding_sprint"):
                await state.set_state(OnboardingSprintStates.paywall)
                await msg.answer(
                    PAYWALL_TEXT,
                    reply_markup=paywall_keyboard(),
                )
            else:
                await state.set_state(AntipanicSession.rating_tension_after)
                await msg.answer(
                    "Отметь, насколько сейчас напряжение (0–10):",
                    reply_markup=tension_keyboard(),
                )

    logger.info(f"Step {step_id} completed by user {user.telegram_id}")


@router.callback_query(StepCallback.filter(F.action == StepAction.skip))
async def step_skip(
    callback: CallbackQuery, callback_data: StepCallback, state: FSMContext
) -> None:
    """
    Пропуск шага — запрашиваем причину.

    AICODE-NOTE: Thin handler - вызывает use-case и показывает результат.
    """
    msg = get_callback_message(callback)
    await callback.answer()

    if not callback.from_user:
        return

    step_id = callback_data.step_id

    current_state = await state.get_state()
    is_antipanic = current_state in (
        AntipanicSession.doing_body_action,
        AntipanicSession.doing_micro_action,
    )

    if is_antipanic:
        # Быстрый пропуск без лишних вопросов для анти-паралич режима
        # 1. Получить пользователя
        user = await user_repo.get_user(callback.from_user.id)
        if not user:
            await msg.edit_text("Пользователь не найден.")
            return

        # 2. Вызвать use-case для пропуска шага
        result = await skip_step_use_case.execute(step_id, user, reason="-")

        if not result.success:
            await msg.edit_text(f"Ошибка: {result.error_message}")
            return

        data = await state.get_data()
        if current_state == AntipanicSession.doing_body_action:
            goal = (
                await Goal.get_or_none(id=data.get("goal_id"), user=user)
                if user
                else None
            )
            if goal:
                micro_step = await session_service.get_task_micro_action(
                    user=user,
                    goal=goal,
                    tension=data.get("tension_before"),
                    max_minutes=5,
                )
                await state.update_data(micro_step_id=micro_step.id)
                await state.set_state(AntipanicSession.doing_micro_action)
                await msg.edit_text(
                    "Ок, тело пропустили. Давай всё равно попробуем микрошаг по задаче:\n"
                    f"👉 {escape_markdown(micro_step.title)}",
                    reply_markup=steps_list_keyboard([micro_step.id]),
                )
            else:
                await msg.edit_text(
                    "Пропустили шаг. Обнови цель через /start, чтобы продолжить."
                )
        else:
            await state.set_state(AntipanicSession.rating_tension_after)
            await msg.edit_text(
                "Принял. Оцени напряжение сейчас (0–10):",
                reply_markup=tension_keyboard(),
            )
        return

    # Не-antipanic режим: запрашиваем причину
    # Получаем шаг для показа названия
    step = await Step.get_or_none(id=step_id)
    if not step:
        await msg.edit_text("Шаг не найден.")
        return

    await state.update_data(skipping_step_id=step_id)
    await state.set_state(EveningStates.waiting_for_skip_reason)

    await msg.edit_text(
        f"Пропускаем: *{escape_markdown(step.title)}*\n\n"
        "Коротко напиши причину (или отправь `-` если не хочешь):"
    )


@router.message(EveningStates.waiting_for_skip_reason)
async def process_skip_reason(message: Message, state: FSMContext) -> None:
    """
    Обработка причины пропуска.

    AICODE-NOTE: Thin handler - вызывает use-case и показывает результат.
    """
    if not message.from_user:
        return

    reason = message.text or "-"
    data = await state.get_data()
    step_id = data.get("skipping_step_id")

    if not step_id:
        await state.clear()
        return

    # 1. Получить пользователя
    user = await user_repo.get_user(message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Пользователь не найден.")
        return

    # 2. Вызвать use-case для пропуска шага
    result = await skip_step_use_case.execute(step_id, user, reason=reason)

    if not result.success:
        await message.answer(f"Ошибка: {result.error_message}")
        await state.clear()
        return

    await state.clear()

    # 3. Показываем обновлённый список
    today = date.today()
    daily_log = await DailyLog.get_or_none(user=user, date=today)
    assigned_ids = daily_log.assigned_step_ids if daily_log else []

    if assigned_ids:
        steps = await Step.filter(id__in=assigned_ids)

        def step_icon(status: str) -> str:
            if status == "completed":
                return "✅"
            elif status == "skipped":
                return "⏭"
            return "⬜"

        steps_text = "\n".join(f"{step_icon(s.status)} {escape_markdown(s.title)}" for s in steps)

        pending_ids = [s.id for s in steps if s.status == "pending"]

        if pending_ids:
            await message.answer(
                f"*Шаги на сегодня:*\n{steps_text}",
                reply_markup=steps_list_keyboard(pending_ids),
            )
        else:
            await message.answer(
                f"*Шаги на сегодня:*\n{steps_text}\n\n"
                "Напиши /evening для подведения итогов."
            )

    logger.info(f"Step {step_id} skipped by user {user.telegram_id}: {reason}")


@router.callback_query(OnboardingSprintStates.paywall, PaywallCallback.filter())
async def handle_paywall_choice(
    callback: CallbackQuery, callback_data: PaywallCallback, state: FSMContext
) -> None:
    """Обработка пейволла после мини-спринта."""
    msg = get_callback_message(callback)
    await callback.answer()

    if not callback.from_user:
        return

    user = await User.get_or_none(telegram_id=callback.from_user.id)
    if not user:
        await state.clear()
        await msg.edit_text(
            "Ошибка: пользователь не найден. Напиши /start"
        )
        return

    if callback_data.action == PaywallAction.accept:
        # Удаляем onboarding goal - будем создавать настоящую цель
        onboarding_goal = await Goal.get_or_none(user=user, status="onboarding")
        if onboarding_goal:
            await onboarding_goal.delete()

        # Переходим к созданию реальной цели
        await state.set_state(OnboardingStates.waiting_for_goal)
        await msg.edit_text(
            "🔥 Отлично! Запускаю 3-дневную миссию.\n\n"
            "Я буду помогать тебе каждый день двигаться маленькими шагами. "
            "Без паралича, без прокрастинации.\n\n"
            "*Какую цель хочешь достичь?*\n"
            "Например: выучить Python, запустить блог, похудеть на 5 кг"
        )
        await msg.answer(
            "Главное меню:",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Пользователь отказался от миссии - удаляем onboarding goal
    onboarding_goal = await Goal.get_or_none(user=user, status="onboarding")
    if onboarding_goal:
        await onboarding_goal.delete()

    await state.clear()
    await msg.edit_text(
        "Окей, без проблем. Когда захочешь начать — жми /start"
    )
    await msg.answer(
        "Главное меню:",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(StepCallback.filter(F.action == StepAction.stuck))
async def step_stuck(
    callback: CallbackQuery, callback_data: StepCallback, state: FSMContext
) -> None:
    """Переход в stuck flow."""
    msg = get_callback_message(callback)
    await callback.answer()

    step_id = callback_data.step_id
    step = await Step.get_or_none(id=step_id)

    if not step:
        await msg.edit_text("Шаг не найден.")
        return

    await state.update_data(stuck_step_id=step_id, stuck_step_title=step.title)
    await state.set_state(StuckStates.waiting_for_blocker)

    # Импортируем клавиатуру здесь чтобы избежать circular import
    from src.bot.keyboards import blocker_keyboard

    await msg.edit_text(
        f"🆘 Застрял на: *{escape_markdown(step.title)}*\n\nЧто мешает?",
        reply_markup=blocker_keyboard(),
    )
