"""
Управление целями и этапами.

Функционал:
- /goals — список целей пользователя
- Редактирование этапов
- Удаление целей с подтверждением
- Пауза/возобновление целей
- Добавление новых этапов
"""

import logging
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.callbacks.data import (
    GoalManageAction,
    GoalManageCallback,
    GoalSelectCallback,
    StageManageAction,
    StageManageCallback,
)
from src.bot.keyboards import (
    confirm_delete_keyboard,
    goal_manage_keyboard,
    main_menu_keyboard,
    stages_manage_keyboard,
)
from src.bot.states import GoalManageStates
from src.database.models import Goal, Stage, User

logger = logging.getLogger(__name__)

router = Router(name="manage_goals")


@router.message(Command("goals"))
@router.message(F.text.casefold().in_(("цели", "мои цели")))
async def cmd_goals(message: Message, state: FSMContext) -> None:
    """Показать список всех целей пользователя."""
    if not message.from_user:
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        await message.answer("Пользователь не найден. Напиши /start")
        return

    # Получаем все цели (кроме удалённых)
    goals = (
        await Goal.filter(user=user).exclude(status="abandoned").order_by("-created_at")
    )

    if not goals:
        await message.answer(
            "У тебя пока нет целей.\nНапиши /start чтобы создать первую.",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Формируем список целей
    text = "*Твои цели:*\n\n"
    for goal in goals:
        status_icon = {
            "active": "🔵",
            "paused": "⏸",
            "completed": "✅",
            "onboarding": "🔨",
        }.get(goal.status, "⚪")

        days_left = (goal.deadline - date.today()).days
        deadline_text = (
            f"до {goal.deadline.strftime('%d.%m.%Y')}"
            if days_left > 0
            else "просрочено"
        )

        text += f"{status_icon} *{goal.title}*\n"
        text += f"   📅 {deadline_text} ({days_left} дн.)\n\n"

    text += "Выбери цель для управления:"

    # Показываем inline кнопки для каждой цели
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    from src.bot.callbacks.data import GoalSelectCallback

    builder = InlineKeyboardBuilder()
    for goal in goals:
        builder.button(
            text=f"{goal.title[:30]}",
            callback_data=GoalSelectCallback(goal_id=goal.id),
        )
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(GoalSelectCallback.filter())
async def on_goal_select(
    callback: CallbackQuery, callback_data: GoalSelectCallback, state: FSMContext
) -> None:
    """Показать детали конкретной цели."""
    goal = await Goal.get_or_none(id=callback_data.goal_id).prefetch_related("stages")

    if not goal:
        await callback.message.edit_text("Цель не найдена.")
        return

    stages = await goal.stages.all().order_by("order")

    # Формируем текст
    text = f"🎯 *{goal.title}*\n\n"
    text += f"📅 Дедлайн: {goal.deadline.strftime('%d.%m.%Y')}\n"
    text += f"📊 Статус: {goal.status}\n\n"

    if stages:
        text += "*Этапы:*\n"
        for i, stage in enumerate(stages, 1):
            icon = (
                "✅"
                if stage.status == "completed"
                else "🔵"
                if stage.status == "active"
                else "⚪"
            )
            text += f"{icon} {i}. {stage.title} ({stage.progress}%)\n"
    else:
        text += "_Нет этапов_\n"

    await state.update_data(current_goal_id=goal.id)
    await state.set_state(GoalManageStates.viewing_goal)

    await callback.message.edit_text(
        text, reply_markup=goal_manage_keyboard(goal.id, goal.status == "active")
    )
    await callback.answer()


@router.callback_query(
    GoalManageCallback.filter(F.action == GoalManageAction.edit_stages)
)
async def on_edit_stages(
    callback: CallbackQuery, callback_data: GoalManageCallback, state: FSMContext
) -> None:
    """Показать список этапов для редактирования."""
    goal = await Goal.get_or_none(id=callback_data.goal_id).prefetch_related("stages")

    if not goal:
        await callback.message.edit_text("Цель не найдена.")
        return

    stages = await goal.stages.all().order_by("order")

    text = "✏️ *Редактирование этапов*\n\n"
    text += f"Цель: _{goal.title}_\n\n"

    if stages:
        text += "Выбери этап для редактирования или добавь новый:"
    else:
        text += "Этапов пока нет. Добавь первый этап:"

    await state.update_data(current_goal_id=goal.id)
    await state.set_state(GoalManageStates.editing_stages)

    await callback.message.edit_text(
        text, reply_markup=stages_manage_keyboard(stages, goal.id)
    )
    await callback.answer()


@router.callback_query(StageManageCallback.filter(F.action == StageManageAction.edit))
async def on_edit_stage_name(
    callback: CallbackQuery, callback_data: StageManageCallback, state: FSMContext
) -> None:
    """Начать редактирование названия этапа."""
    stage = await Stage.get_or_none(id=callback_data.stage_id)

    if not stage:
        await callback.message.edit_text("Этап не найден.")
        return

    await state.update_data(
        current_goal_id=callback_data.goal_id, current_stage_id=stage.id
    )
    await state.set_state(GoalManageStates.editing_stage_name)

    await callback.message.edit_text(
        f"Текущее название: *{stage.title}*\n\n"
        "Введи новое название этапа (или /cancel для отмены):"
    )
    await callback.answer()


@router.message(GoalManageStates.editing_stage_name)
async def process_stage_name(message: Message, state: FSMContext) -> None:
    """Сохранить новое название этапа."""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return

    data = await state.get_data()
    stage_id = data.get("current_stage_id")
    goal_id = data.get("current_goal_id")

    stage = await Stage.get_or_none(id=stage_id)
    if not stage:
        await message.answer("Этап не найден.")
        return

    old_title = stage.title
    stage.title = message.text
    await stage.save()

    await message.answer(
        f"✅ Название изменено:\nБыло: _{old_title}_\nСтало: *{stage.title}*",
    )

    # Возвращаемся к списку этапов
    goal = await Goal.get_or_none(id=goal_id).prefetch_related("stages")
    stages = await goal.stages.all().order_by("order")

    await state.set_state(GoalManageStates.editing_stages)
    await message.answer(
        f"Этапы цели _{goal.title}_:",
        reply_markup=stages_manage_keyboard(stages, goal_id),
    )


@router.callback_query(StageManageCallback.filter(F.action == StageManageAction.add))
async def on_add_stage(
    callback: CallbackQuery, callback_data: StageManageCallback, state: FSMContext
) -> None:
    """Начать добавление нового этапа."""
    await state.update_data(current_goal_id=callback_data.goal_id)
    await state.set_state(GoalManageStates.adding_stage)

    await callback.message.edit_text(
        "➕ *Новый этап*\n\nВведи название нового этапа (или /cancel для отмены):"
    )
    await callback.answer()


@router.message(GoalManageStates.adding_stage)
async def process_new_stage(message: Message, state: FSMContext) -> None:
    """Создать новый этап."""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=main_menu_keyboard())
        return

    data = await state.get_data()
    goal_id = data.get("current_goal_id")

    goal = await Goal.get_or_none(id=goal_id).prefetch_related("stages")
    if not goal:
        await message.answer("Цель не найдена.")
        return

    # Определяем order для нового этапа
    stages = await goal.stages.all().order_by("order")
    max_order = max([s.order for s in stages]) if stages else 0

    # Создаём новый этап
    new_stage = await Stage.create(
        goal=goal,
        title=message.text,
        order=max_order + 1,
        start_date=date.today(),
        end_date=goal.deadline,
        status="pending",  # Новые этапы pending по умолчанию
        progress=0,
    )

    await message.answer(f"✅ Этап *{new_stage.title}* добавлен!")

    # Обновляем список этапов (перезагружаем goal с prefetch)
    goal = await Goal.get_or_none(id=goal_id).prefetch_related("stages")
    stages = await goal.stages.all().order_by("order")
    await state.set_state(GoalManageStates.editing_stages)
    await message.answer(
        f"Этапы цели _{goal.title}_:",
        reply_markup=stages_manage_keyboard(stages, goal_id),
    )


@router.callback_query(StageManageCallback.filter(F.action == StageManageAction.delete))
async def on_delete_stage(
    callback: CallbackQuery, callback_data: StageManageCallback, state: FSMContext
) -> None:
    """Подтверждение удаления этапа."""
    stage = await Stage.get_or_none(id=callback_data.stage_id)

    if not stage:
        await callback.message.edit_text("Этап не найден.")
        return

    # Проверка: если это последний этап, предупреждаем
    goal = await Goal.get_or_none(id=callback_data.goal_id)
    stages_count = await Stage.filter(goal=goal).count()

    if stages_count == 1:
        await callback.message.edit_text(
            f"⚠️ *{stage.title}* — последний этап цели.\n\n"
            "Удалить его нельзя. Если хочешь удалить цель целиком, "
            "вернись назад и выбери 'Удалить цель'."
        )
        await callback.answer()
        return

    await state.update_data(
        current_goal_id=callback_data.goal_id, current_stage_id=stage.id
    )
    await state.set_state(GoalManageStates.confirming_delete_stage)

    await callback.message.edit_text(
        f"🗑 *Удалить этап?*\n\n"
        f"Этап: _{stage.title}_\n"
        f"Прогресс: {stage.progress}%\n\n"
        "⚠️ Это действие нельзя отменить.",
        reply_markup=confirm_delete_keyboard(callback_data.goal_id, stage.id),
    )
    await callback.answer()


@router.callback_query(
    GoalManageCallback.filter(F.action == GoalManageAction.delete),
    GoalManageStates.confirming_delete_stage,
)
async def confirm_delete_stage(
    callback: CallbackQuery, callback_data: GoalManageCallback, state: FSMContext
) -> None:
    """Выполнить удаление этапа."""
    data = await state.get_data()
    stage_id = data.get("current_stage_id")
    goal_id = data.get("current_goal_id")

    stage = await Stage.get_or_none(id=stage_id)
    if not stage:
        await callback.message.edit_text("Этап не найден.")
        return

    title = stage.title
    await stage.delete()

    await callback.message.edit_text(f"✅ Этап _{title}_ удалён.")

    # Возвращаемся к списку этапов
    goal = await Goal.get_or_none(id=goal_id).prefetch_related("stages")
    stages = await goal.stages.all().order_by("order")

    await state.set_state(GoalManageStates.editing_stages)
    await callback.message.answer(
        f"Этапы цели _{goal.title}_:",
        reply_markup=stages_manage_keyboard(stages, goal_id),
    )
    await callback.answer()


@router.callback_query(GoalManageCallback.filter(F.action == GoalManageAction.pause))
async def on_pause_goal(
    callback: CallbackQuery, callback_data: GoalManageCallback, state: FSMContext
) -> None:
    """Приостановить цель."""
    goal = await Goal.get_or_none(id=callback_data.goal_id)

    if not goal:
        await callback.message.edit_text("Цель не найдена.")
        return

    goal.status = "paused"
    await goal.save()

    await callback.message.edit_text(
        f"⏸ Цель *{goal.title}* приостановлена.\n\n"
        "Можешь возобновить её в любое время через /goals."
    )
    await callback.answer()


@router.callback_query(GoalManageCallback.filter(F.action == GoalManageAction.resume))
async def on_resume_goal(
    callback: CallbackQuery, callback_data: GoalManageCallback, state: FSMContext
) -> None:
    """Возобновить цель."""
    goal = await Goal.get_or_none(id=callback_data.goal_id)

    if not goal:
        await callback.message.edit_text("Цель не найдена.")
        return

    goal.status = "active"
    await goal.save()

    await callback.message.edit_text(
        f"▶️ Цель *{goal.title}* возобновлена!\n\nЖми *Утро* — спланируем день.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(GoalManageCallback.filter(F.action == GoalManageAction.complete))
async def on_complete_goal(
    callback: CallbackQuery, callback_data: GoalManageCallback, state: FSMContext
) -> None:
    """Завершить цель."""
    goal = await Goal.get_or_none(id=callback_data.goal_id)

    if not goal:
        await callback.message.edit_text("Цель не найдена.")
        return

    goal.status = "completed"
    await goal.save()

    await callback.message.edit_text(
        f"🎉 *Цель достигнута!*\n\n"
        f"_{goal.title}_\n\n"
        "Поздравляю! Создавай новую цель через /start.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    GoalManageCallback.filter(F.action == GoalManageAction.delete),
    GoalManageStates.viewing_goal,
)
async def on_delete_goal_confirm(
    callback: CallbackQuery, callback_data: GoalManageCallback, state: FSMContext
) -> None:
    """Подтверждение удаления цели."""
    goal = await Goal.get_or_none(id=callback_data.goal_id)

    if not goal:
        await callback.message.edit_text("Цель не найдена.")
        return

    await state.update_data(current_goal_id=goal.id)
    await state.set_state(GoalManageStates.confirming_delete_goal)

    await callback.message.edit_text(
        f"🗑 *Удалить цель?*\n\n"
        f"Цель: _{goal.title}_\n\n"
        "⚠️ Все этапы и шаги будут удалены.\n"
        "Это действие нельзя отменить.",
        reply_markup=confirm_delete_keyboard(goal.id),
    )
    await callback.answer()


@router.callback_query(
    GoalManageCallback.filter(F.action == GoalManageAction.delete),
    GoalManageStates.confirming_delete_goal,
)
async def confirm_delete_goal(
    callback: CallbackQuery, callback_data: GoalManageCallback, state: FSMContext
) -> None:
    """Выполнить удаление цели."""
    goal = await Goal.get_or_none(id=callback_data.goal_id).prefetch_related("stages")

    if not goal:
        await callback.message.edit_text("Цель не найдена.")
        return

    title = goal.title

    # Удаляем все этапы (каскадное удаление шагов происходит автоматически через FK)
    stages = await goal.stages.all()
    for stage in stages:
        await stage.delete()

    # Удаляем цель
    await goal.delete()

    await state.clear()
    await callback.message.edit_text(
        f"✅ Цель _{title}_ и все её этапы удалены.\n\nСоздай новую цель через /start.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
