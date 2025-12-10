"""
Legacy morning check-in flow (kept for reference/backward compatibility).
New antiparalysis flow lives in src/bot/handlers/morning.py.
"""

from datetime import date
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.bot.states import MorningStates
from src.bot.keyboards import (
    energy_keyboard,
    simple_energy_keyboard,
    steps_list_keyboard,
    low_energy_keyboard,
    main_menu_keyboard,
)
from src.bot.callbacks.data import (
    EnergyCallback,
    SimpleEnergyCallback,
    EnergyLevel,
    QuickStepCallback,
    QuickStepAction,
)
from src.database.models import User, Goal, Stage, Step, DailyLog
from src.services.ai import ai_service

logger = logging.getLogger(__name__)

router = Router(name="legacy_morning")


@router.message(F.text.casefold().in_(("утро", "/morning_legacy")))
async def morning_from_menu(message: Message, state: FSMContext) -> None:
    """Legacy support via /morning_legacy."""
    await cmd_morning(message, state)


@router.message(Command("morning_legacy"))
async def cmd_morning(message: Message, state: FSMContext) -> None:
    """Начало утреннего ритуала (legacy)."""
    if not message.from_user:
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        await message.answer("Сначала напиши /start чтобы создать цель.")
        return

    # Проверяем активную цель
    active_goal = await Goal.filter(user=user, status="active").first()
    if not active_goal:
        await message.answer(
            "У тебя нет активной цели.\n" "Напиши /start чтобы создать.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Проверяем, не было ли уже утреннего чек-ина сегодня
    today = date.today()
    existing_log = await DailyLog.get_or_none(user=user, date=today)
    if existing_log and existing_log.energy_level:
        # Уже был чек-ин — проверяем, все ли шаги выполнены
        step_ids = existing_log.assigned_step_ids or []
        if step_ids:
            steps = await Step.filter(id__in=step_ids)
            pending_steps = [s for s in steps if s.status == "pending"]

            # Если все шаги выполнены — проверяем, не пора ли к новому этапу
            if not pending_steps:
                # Проверяем текущий активный этап
                current_stage = await Stage.filter(
                    goal=active_goal, status="active"
                ).first()
                if current_stage and current_stage.progress >= 100:
                    # Этап завершён! Переключаемся на следующий
                    current_stage.status = "completed"
                    await current_stage.save()
                    logger.info(
                        f"Stage '{current_stage.title}' completed via morning check"
                    )

                    # Ищем следующий этап
                    next_stage = (
                        await Stage.filter(goal=active_goal, status="pending")
                        .order_by("order")
                        .first()
                    )

                    if next_stage:
                        next_stage.status = "active"
                        await next_stage.save()
                        logger.info(f"Activated new stage: '{next_stage.title}'")

                        await message.answer(
                            f"🎉 *Этап «{current_stage.title}» завершён!*\n\n"
                            f"Переходим к следующему: *{next_stage.title}*\n\n"
                            "Хочешь запланировать шаги на новый этап?",
                            reply_markup=energy_keyboard(),
                        )
                        await state.set_state(MorningStates.waiting_for_energy)
                        return
                    else:
                        # Все этапы завершены!
                        active_goal.status = "completed"
                        await active_goal.save()
                        await message.answer(
                            f"🏆 *Поздравляю! Цель «{active_goal.title}» достигнута!*\n\n"
                            "Все этапы завершены. Напиши /start для новой цели."
                        )
                        return

                # Все шаги сделаны, но этап ещё не 100%
                steps_text = "\n".join(f"✅ {s.title}" for s in steps)
                await message.answer(
                    "Утренний чек-ин на сегодня уже есть. "
                    "Можешь отметить шаги ниже или посмотреть статус.\n\n"
                    f"*Выполнено:*\n{steps_text}\n\n"
                    "Отдыхай, завтра продолжим! 💪",
                    reply_markup=main_menu_keyboard(),
                )
                return

            # Есть невыполненные шаги
            steps_text = "\n".join(
                f"{'✅' if s.status == 'completed' else '⬜'} {s.title}" for s in steps
            )
            pending_ids = [s.id for s in pending_steps]
            await message.answer(
                "Утренний чек-ин на сегодня уже есть. "
                "Можешь отметить шаги ниже или посмотреть статус.\n\n"
                f"*Шаги на сегодня:*\n{steps_text}\n\n"
                "Используй кнопки ниже для отметки:",
                reply_markup=steps_list_keyboard(pending_ids),
            )
        else:
            await message.answer(
                "Утренний чек-ин на сегодня уже есть. Шагов сегодня нет.",
                reply_markup=main_menu_keyboard(),
            )
        return

    await state.set_state(MorningStates.waiting_for_energy)

    await message.answer(
        "🌅 *Как ты сегодня?*", reply_markup=simple_energy_keyboard()
    )


@router.callback_query(MorningStates.waiting_for_energy, SimpleEnergyCallback.filter())
async def process_simple_energy(
    callback: CallbackQuery, callback_data: SimpleEnergyCallback, state: FSMContext
) -> None:
    """
    Упрощённый выбор энергии (3 уровня).
    При низкой энергии — сразу микрошаг.
    При средней/высокой — генерация шагов без ввода настроения.
    """
    await callback.answer()

    level = callback_data.level

    # Маппинг уровня в числовое значение для AI
    energy_map = {
        EnergyLevel.low: 2,
        EnergyLevel.medium: 5,
        EnergyLevel.high: 8,
    }
    energy = energy_map[level]

    if not callback.from_user:
        return

    user = await User.get_or_none(telegram_id=callback.from_user.id)
    if not user:
        await state.clear()
        await callback.message.edit_text("Напиши /start чтобы начать.")
        return

    active_goal = await Goal.filter(user=user, status="active").first()
    if not active_goal:
        await state.clear()
        await callback.message.edit_text(
            "Цель не найдена. Напиши /start", reply_markup=main_menu_keyboard()
        )
        return

    # Получаем текущий этап
    current_stage = await Stage.filter(goal=active_goal, status="active").first()

    if current_stage and current_stage.progress >= 100:
        current_stage.status = "completed"
        await current_stage.save()
        current_stage = None

    if not current_stage:
        current_stage = (
            await Stage.filter(goal=active_goal, status="pending")
            .order_by("order")
            .first()
        )
        if current_stage:
            current_stage.status = "active"
            await current_stage.save()
        else:
            # Все этапы завершены
            completed_count = await Stage.filter(
                goal=active_goal, status="completed"
            ).count()
            total_count = await Stage.filter(goal=active_goal).count()

            if completed_count == total_count:
                active_goal.status = "completed"
                await active_goal.save()
                await state.clear()
                await callback.message.edit_text(
                    f"🎉 *Цель «{active_goal.title}» достигнута!*\n\n"
                    "Напиши /start для новой цели."
                )
                return

            await state.clear()
            await callback.message.edit_text(
                "Нет активных этапов. Напиши /start",
                reply_markup=main_menu_keyboard(),
            )
            return

    # === НИЗКАЯ ЭНЕРГИЯ: сразу микрошаг ===
    if level == EnergyLevel.low:
        wait_msg = await callback.message.edit_text("⏳ Подбираю микрошаг...")

        micro_step_text = await ai_service.generate_micro_step(
            stage_title=current_stage.title, energy=energy, mood="мало сил"
        )

        today = date.today()
        micro_step = await Step.create(
            stage=current_stage,
            title=micro_step_text,
            difficulty="easy",
            estimated_minutes=2,
            xp_reward=5,
            scheduled_date=today,
            status="pending",
        )

        # Создаём/обновляем DailyLog
        daily_log, _ = await DailyLog.get_or_create(
            user=user,
            date=today,
            defaults={
                "energy_level": energy,
                "mood_text": "мало сил",
                "assigned_step_ids": [micro_step.id],
            },
        )
        if not daily_log.assigned_step_ids:
            daily_log.energy_level = energy
            daily_log.assigned_step_ids = [micro_step.id]
            await daily_log.save()

        await state.clear()

        await wait_msg.edit_text(
            f"😴 Понял, энергии мало.\n\n"
            f"*Твой микрошаг на 2 минуты:*\n"
            f"👉 {micro_step_text}\n\n"
            "Сделай только это — и день уже не зря.",
            reply_markup=steps_list_keyboard([micro_step.id]),
        )

        logger.info(
            f"Low energy micro-step for user {user.telegram_id}: '{micro_step_text[:40]}...'"
        )
        return

    # === СРЕДНЯЯ/ВЫСОКАЯ ЭНЕРГИЯ: генерация шагов ===
    wait_msg = await callback.message.edit_text("⏳ Планирую шаги...")

    mood = "нормально" if level == EnergyLevel.medium else "бодро"
    steps_data = await ai_service.generate_steps(
        stage_title=current_stage.title, energy=energy, mood=mood
    )

    today = date.today()
    created_steps = []

    for step_info in steps_data:
        difficulty = step_info.get("difficulty", "medium")
        minutes = step_info.get("minutes", 15)
        xp_map = {"easy": 10, "medium": 20, "hard": 40}
        xp = xp_map.get(difficulty, 20)

        step = await Step.create(
            stage=current_stage,
            title=step_info["title"],
            difficulty=difficulty,
            estimated_minutes=minutes,
            xp_reward=xp,
            scheduled_date=today,
            status="pending",
        )
        created_steps.append(step)

    step_ids = [s.id for s in created_steps]

    daily_log, _ = await DailyLog.get_or_create(
        user=user,
        date=today,
        defaults={
            "energy_level": energy,
            "mood_text": mood,
            "assigned_step_ids": step_ids,
        },
    )
    if not daily_log.assigned_step_ids:
        daily_log.energy_level = energy
        daily_log.mood_text = mood
        daily_log.assigned_step_ids = step_ids
        await daily_log.save()

    # Формируем текст шагов
    steps_text = ""
    for i, step in enumerate(created_steps, 1):
        diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(
            step.difficulty, "🟡"
        )
        steps_text += f"{i}. {step.title} {diff_emoji} ~{step.estimated_minutes}мин\n"

    await state.clear()

    level_text = "😐" if level == EnergyLevel.medium else "⚡"
    await wait_msg.edit_text(
        f"{level_text} *Шаги на сегодня:*\n\n"
        f"{steps_text}\n"
        f"📍 Этап: _{current_stage.title}_",
        reply_markup=steps_list_keyboard(step_ids),
    )

    logger.info(
        f"Morning check-in for user {user.telegram_id}: "
        f"energy={level.value}, steps={len(created_steps)}"
    )


@router.callback_query(MorningStates.waiting_for_energy, EnergyCallback.filter())
async def process_energy(
    callback: CallbackQuery, callback_data: EnergyCallback, state: FSMContext
) -> None:
    """Обработка выбора энергии (legacy 1-10, для совместимости)."""
    await callback.answer()

    energy = callback_data.value
    await state.update_data(energy=energy)
    await state.set_state(MorningStates.waiting_for_mood)

    energy_emoji = "🔋" * (energy // 2) + "🪫" * (5 - energy // 2)

    await callback.message.edit_text(
        f"Энергия: *{energy}/10* {energy_emoji}\n\n"
        "Как ты себя чувствуешь? Опиши одним-двумя словами.\n"
        "Например: _тревожно_, _бодро_, _сонно_, _нормально_"
    )


@router.message(MorningStates.waiting_for_mood)
async def process_mood(message: Message, state: FSMContext) -> None:
    """Обработка настроения и генерация шагов."""
    if not message.from_user:
        return

    mood = message.text or "нормально"
    data = await state.get_data()
    energy = data.get("energy")

    if energy is None:
        await state.set_state(MorningStates.waiting_for_energy)
        await message.answer(
            "Не вижу выбранную энергию. Выбери уровень снова:",
            reply_markup=energy_keyboard(),
        )
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        await state.clear()
        await message.answer("Не нашёл профиль. Напиши /start чтобы создать цель.")
        return
    active_goal = await Goal.filter(user=user, status="active").first()

    if not active_goal:
        await state.clear()
        await message.answer("Цель не найдена. Напиши /start")
        return

    # Получаем текущий активный этап с проверкой завершённости
    current_stage = await Stage.filter(goal=active_goal, status="active").first()

    # Если активный этап завершён (100%) — переключаемся на следующий
    if current_stage and current_stage.progress >= 100:
        current_stage.status = "completed"
        await current_stage.save()
        logger.info(f"Stage '{current_stage.title}' completed, switching to next")
        current_stage = None  # Искать следующий

    if not current_stage:
        # Активируем первый pending этап
        current_stage = (
            await Stage.filter(goal=active_goal, status="pending")
            .order_by("order")
            .first()
        )

        if current_stage:
            current_stage.status = "active"
            await current_stage.save()
            logger.info(f"Activated new stage: '{current_stage.title}'")
        else:
            # Проверяем, может все этапы completed
            completed_stages = await Stage.filter(
                goal=active_goal, status="completed"
            ).count()
            total_stages = await Stage.filter(goal=active_goal).count()

            if completed_stages == total_stages:
                # Цель достигнута!
                active_goal.status = "completed"
                await active_goal.save()
                await state.clear()
                await message.answer(
                    "🎉 *Поздравляю! Цель достигнута!*\n\n"
                    f"Ты завершил все этапы цели «{active_goal.title}»!\n\n"
                    "Напиши /start для новой цели."
                )
                return
            else:
                await state.clear()
                await message.answer(
                    "🤔 Не нашёл активных этапов.\n"
                    "Напиши /start чтобы проверить статус."
                )
                return

    # Генерируем шаги через AI
    wait_msg = await message.answer("🤔 Планирую шаги на день...")

    steps_data = await ai_service.generate_steps(
        stage_title=current_stage.title, energy=energy, mood=mood
    )

    # Создаём шаги в БД
    today = date.today()
    created_steps = []

    for step_info in steps_data:
        difficulty = step_info.get("difficulty", "medium")
        minutes = step_info.get("minutes", 15)

        # XP зависит от сложности
        xp_map = {"easy": 10, "medium": 20, "hard": 40}
        xp = xp_map.get(difficulty, 20)

        step = await Step.create(
            stage=current_stage,
            title=step_info["title"],
            difficulty=difficulty,
            estimated_minutes=minutes,
            xp_reward=xp,
            scheduled_date=today,
            status="pending",
        )
        created_steps.append(step)

    step_ids = [s.id for s in created_steps]

    # Создаём или обновляем DailyLog
    daily_log, _ = await DailyLog.get_or_create(
        user=user,
        date=today,
        defaults={
            "energy_level": energy,
            "mood_text": mood,
            "assigned_step_ids": step_ids,
        },
    )
    if daily_log.energy_level is None:
        daily_log.energy_level = energy
        daily_log.mood_text = mood
        daily_log.assigned_step_ids = step_ids
        await daily_log.save()

    await wait_msg.delete()

    # Формируем текст шагов
    steps_text = ""
    for i, step in enumerate(created_steps, 1):
        diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(
            step.difficulty, "🟡"
        )
        steps_text += f"{i}. {step.title} {diff_emoji} ~{step.estimated_minutes}мин\n"

    # Если энергия низкая (<=3), предлагаем микрошаг
    if energy <= 3:
        await state.update_data(
            stage_title=current_stage.title,
            energy=energy,
            mood=mood,
            step_ids=step_ids,
        )
        await state.set_state(MorningStates.waiting_for_quick_step)

        await message.answer(
            f"📍 Этап: _{current_stage.title}_\n"
            f"⚡ Энергия: {energy}/10\n\n"
            f"Вижу, что энергии мало. Окей, давай не геройствовать.\n\n"
            f"*Предлагаю такие шаги:*\n{steps_text}\n\n"
            "Хочешь вместо этого один микро-шаг максимум на 2 минуты?",
            reply_markup=low_energy_keyboard(),
        )
    else:
        await state.clear()
        await message.answer(
            f"✨ *План на день готов!*\n\n"
            f"📍 Этап: _{current_stage.title}_\n"
            f"⚡ Энергия: {energy}/10\n\n"
            f"*Шаги:*\n{steps_text}\n"
            "Отмечай выполнение кнопками ниже:",
            reply_markup=steps_list_keyboard(step_ids),
        )

    logger.info(
        f"Morning check-in for user {user.telegram_id}: "
        f"energy={energy}, steps={len(created_steps)}"
    )


@router.callback_query(MorningStates.waiting_for_quick_step, QuickStepCallback.filter())
async def process_quick_step_choice(
    callback: CallbackQuery, callback_data: QuickStepCallback, state: FSMContext
) -> None:
    """Обработка выбора: микрошаг или обычные шаги."""
    await callback.answer()

    data = await state.get_data()
    step_ids = data.get("step_ids", [])

    if callback_data.action == QuickStepAction.keep:
        # Оставить как есть — показываем обычные шаги
        await state.clear()
        await callback.message.edit_text(
            f"{callback.message.text}\n\n"
            "Хорошо, оставляю план как есть. Отмечай выполнение кнопками ниже:",
            reply_markup=steps_list_keyboard(step_ids),
        )
        return

    # Генерируем микрошаг
    stage_title = data.get("stage_title", "")
    energy = data.get("energy", 1)
    mood = data.get("mood", "")

    if not callback.from_user:
        return

    user = await User.get_or_none(telegram_id=callback.from_user.id)
    if not user:
        await state.clear()
        await callback.message.edit_text("Не нашёл профиль.")
        return

    wait_msg = await callback.message.edit_text(
        f"{callback.message.text}\n\n⏳ Формулирую микрошаг..."
    )

    # Генерируем микрошаг через AI
    micro_step_text = await ai_service.generate_micro_step(
        stage_title=stage_title, energy=energy, mood=mood
    )

    # Создаём микрошаг в БД
    active_goal = await Goal.filter(user=user, status="active").first()
    if not active_goal:
        await state.clear()
        await wait_msg.edit_text("Цель не найдена.")
        return

    current_stage = await Stage.filter(goal=active_goal, status="active").first()
    if not current_stage:
        await state.clear()
        await wait_msg.edit_text("Этап не найден.")
        return

    today = date.today()
    micro_step = await Step.create(
        stage=current_stage,
        title=micro_step_text,
        difficulty="easy",
        estimated_minutes=2,
        xp_reward=5,
        scheduled_date=today,
        status="pending",
    )

    # Обновляем DailyLog: добавляем микрошаг к списку (сохраняя оригинальные)
    daily_log = await DailyLog.get_or_none(user=user, date=today)
    original_step_ids = []
    if daily_log:
        original_step_ids = daily_log.assigned_step_ids or []
        # Добавляем микрошаг к существующим шагам, а не заменяем
        daily_log.assigned_step_ids = original_step_ids + [micro_step.id]
        await daily_log.save()

    await state.clear()

    # Проверяем, были ли уже выполнены оригинальные шаги
    completed_original = []
    if original_step_ids:
        original_steps = await Step.filter(id__in=original_step_ids, status="completed")
        completed_original = list(original_steps)

    # Формируем сообщение с учётом выполненных оригинальных шагов
    message_text = (
        f"⚡ *Супер-микрошаг на 2 минуты:*\n\n"
        f"👉 {micro_step_text}\n\n"
        "Потратишь 1–2 минуты, но мозг вспомнит, что проект существует 😉\n\n"
    )

    if completed_original:
        completed_text = "\n".join(f"✅ {s.title}" for s in completed_original)
        message_text += f"*Уже сделано сегодня:*\n{completed_text}\n\n"

    message_text += "Отметь микрошаг, когда сделаешь:"

    await wait_msg.edit_text(
        message_text, reply_markup=steps_list_keyboard([micro_step.id])
    )

    logger.info(
        f"Micro-step generated for user {user.telegram_id}: "
        f"energy={energy}, step='{micro_step_text[:50]}...'"
    )

