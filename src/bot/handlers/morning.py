"""
Morning handlers — утренний ритуал.

Flow:
1. /morning → проверка активной цели
2. Выбор энергии (1-10)
3. Ввод состояния/настроения
4. AI генерирует шаги на день
5. Создание Step + DailyLog в БД
"""

from datetime import date
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.bot.states import MorningStates
from src.bot.keyboards import energy_keyboard, steps_list_keyboard, low_energy_keyboard
from src.bot.callbacks.data import EnergyCallback, QuickStepCallback, QuickStepAction
from src.database.models import User, Goal, Stage, Step, DailyLog
from src.services.ai import ai_service

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("morning"))
async def cmd_morning(message: Message, state: FSMContext) -> None:
    """Начало утреннего ритуала."""
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
            "У тебя нет активной цели.\n" "Напиши /start чтобы создать."
        )
        return

    # Проверяем, не было ли уже утреннего чек-ина сегодня
    today = date.today()
    existing_log = await DailyLog.get_or_none(user=user, date=today)
    if existing_log and existing_log.energy_level:
        # Уже был чек-ин — показываем шаги
        step_ids = existing_log.assigned_step_ids or []
        if step_ids:
            steps = await Step.filter(id__in=step_ids)
            steps_text = "\n".join(
                f"{'✅' if s.status == 'completed' else '⬜'} {s.title}" for s in steps
            )
            await message.answer(
                f"🌅 Ты уже начал день!\n\n"
                f"*Шаги на сегодня:*\n{steps_text}\n\n"
                "Используй кнопки ниже для отметки:",
                reply_markup=steps_list_keyboard(step_ids),
            )
        else:
            await message.answer("Ты уже отметился сегодня. Шагов нет.")
        return

    await state.set_state(MorningStates.waiting_for_energy)

    await message.answer(
        "🌅 *Доброе утро!*\n\n"
        "Как твоя энергия сегодня?\n"
        "Выбери от 1 (совсем нет сил) до 10 (бодрость максимум):",
        reply_markup=energy_keyboard(),
    )


@router.callback_query(MorningStates.waiting_for_energy, EnergyCallback.filter())
async def process_energy(
    callback: CallbackQuery, callback_data: EnergyCallback, state: FSMContext
) -> None:
    """Обработка выбора энергии."""
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

    # Получаем текущий активный этап
    current_stage = await Stage.filter(goal=active_goal, status="active").first()

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
        else:
            await state.clear()
            await message.answer(
                "🎉 Все этапы завершены! Цель достигнута?\n"
                "Напиши /start для новой цели."
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
