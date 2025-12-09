"""
Steps handlers — действия с шагами.

Callback actions:
- done: отметка выполнения
- skip: пропуск с причиной
- stuck: переход в stuck flow
"""

from datetime import date, datetime
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from src.bot.callbacks.data import StepCallback, StepAction
from src.bot.keyboards import steps_list_keyboard
from src.bot.states import StuckStates, EveningStates
from src.database.models import User, Step, DailyLog

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(StepCallback.filter(F.action == StepAction.done))
async def step_done(callback: CallbackQuery, callback_data: StepCallback) -> None:
    """Отметка шага как выполненного."""
    await callback.answer("✅ Отлично!")

    step_id = callback_data.step_id
    step = await Step.get_or_none(id=step_id)

    if not step:
        await callback.message.edit_text("Шаг не найден.")
        return

    # Обновляем статус шага
    step.status = "completed"
    step.completed_at = datetime.now()
    await step.save()

    # Обновляем DailyLog
    if not callback.from_user:
        return

    user = await User.get(telegram_id=callback.from_user.id)
    today = date.today()
    daily_log = await DailyLog.get_or_none(user=user, date=today)

    if daily_log:
        completed = daily_log.completed_step_ids or []
        if step_id not in completed:
            completed.append(step_id)
            daily_log.completed_step_ids = completed
            daily_log.xp_earned = (daily_log.xp_earned or 0) + step.xp_reward
            await daily_log.save()

    # Начисляем XP пользователю
    user.xp += step.xp_reward
    await user.save()

    # Обновляем сообщение
    assigned_ids = daily_log.assigned_step_ids if daily_log else []
    if assigned_ids:
        steps = await Step.filter(id__in=assigned_ids)
        steps_text = "\n".join(
            f"{'✅' if s.status == 'completed' else '⬜'} {s.title}" for s in steps
        )

        all_done = all(s.status == "completed" for s in steps)

        if all_done:
            await callback.message.edit_text(
                f"🎉 *Все шаги выполнены!*\n\n{steps_text}\n\n"
                f"+{step.xp_reward} XP (всего: {user.xp})\n\n"
                "Отличная работа! Вечером напиши /evening для итогов."
            )
        else:
            await callback.message.edit_text(
                f"*Шаги на сегодня:*\n{steps_text}\n\n" f"+{step.xp_reward} XP",
                reply_markup=steps_list_keyboard(assigned_ids),
            )

    logger.info(f"Step {step_id} completed by user {user.telegram_id}")


@router.callback_query(StepCallback.filter(F.action == StepAction.skip))
async def step_skip(
    callback: CallbackQuery, callback_data: StepCallback, state: FSMContext
) -> None:
    """Пропуск шага — запрашиваем причину."""
    await callback.answer()

    step_id = callback_data.step_id
    step = await Step.get_or_none(id=step_id)

    if not step:
        await callback.message.edit_text("Шаг не найден.")
        return

    await state.update_data(skipping_step_id=step_id)
    await state.set_state(EveningStates.waiting_for_skip_reason)

    await callback.message.edit_text(
        f"Пропускаем: *{step.title}*\n\n"
        "Коротко напиши причину (или отправь `-` если не хочешь):"
    )


@router.message(EveningStates.waiting_for_skip_reason)
async def process_skip_reason(message: Message, state: FSMContext) -> None:
    """Обработка причины пропуска."""
    if not message.from_user:
        return

    reason = message.text or "-"
    data = await state.get_data()
    step_id = data.get("skipping_step_id")

    if not step_id:
        await state.clear()
        return

    step = await Step.get_or_none(id=step_id)
    if step:
        step.status = "skipped"
        await step.save()

    # Обновляем DailyLog
    user = await User.get(telegram_id=message.from_user.id)
    today = date.today()
    daily_log = await DailyLog.get_or_none(user=user, date=today)

    if daily_log:
        skip_reasons = daily_log.skip_reasons or {}
        skip_reasons[str(step_id)] = reason
        daily_log.skip_reasons = skip_reasons
        await daily_log.save()

    await state.clear()

    # Показываем обновлённый список
    assigned_ids = daily_log.assigned_step_ids if daily_log else []
    if assigned_ids:
        steps = await Step.filter(id__in=assigned_ids)

        def step_icon(status: str) -> str:
            if status == "completed":
                return "✅"
            elif status == "skipped":
                return "⏭"
            return "⬜"

        steps_text = "\n".join(f"{step_icon(s.status)} {s.title}" for s in steps)

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


@router.callback_query(StepCallback.filter(F.action == StepAction.stuck))
async def step_stuck(
    callback: CallbackQuery, callback_data: StepCallback, state: FSMContext
) -> None:
    """Переход в stuck flow."""
    await callback.answer()

    step_id = callback_data.step_id
    step = await Step.get_or_none(id=step_id)

    if not step:
        await callback.message.edit_text("Шаг не найден.")
        return

    await state.update_data(stuck_step_id=step_id, stuck_step_title=step.title)
    await state.set_state(StuckStates.waiting_for_blocker)

    # Импортируем клавиатуру здесь чтобы избежать circular import
    from src.bot.keyboards import blocker_keyboard

    await callback.message.edit_text(
        f"🆘 Застрял на: *{step.title}*\n\n" "Что мешает?",
        reply_markup=blocker_keyboard(),
    )
