"""
Weekly report handler — статистика за неделю.

/weekly — агрегация DailyLog за 7 дней
"""

from datetime import date, timedelta
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.database.models import User, Goal, DailyLog

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("weekly"))
async def cmd_weekly(message: Message) -> None:
    """Показать статистику за неделю."""
    if not message.from_user:
        return

    user = await User.get_or_none(telegram_id=message.from_user.id)
    if not user:
        await message.answer("Сначала напиши /start")
        return

    today = date.today()
    week_ago = today - timedelta(days=7)

    # Получаем логи за неделю
    logs = await DailyLog.filter(
        user=user, date__gte=week_ago, date__lte=today
    ).order_by("date")

    if not logs:
        await message.answer(
            "📊 *Статистика за неделю*\n\n"
            "Пока нет данных. Начни использовать /morning каждый день!"
        )
        return

    # Агрегируем статистику
    total_steps_assigned = 0
    total_steps_completed = 0
    total_xp = 0
    energy_values = []
    active_days = 0

    for log in logs:
        if log.assigned_step_ids:
            total_steps_assigned += len(log.assigned_step_ids)
            active_days += 1
        if log.completed_step_ids:
            total_steps_completed += len(log.completed_step_ids)
        if log.xp_earned:
            total_xp += log.xp_earned
        if log.energy_level:
            energy_values.append(log.energy_level)

    avg_energy = sum(energy_values) / len(energy_values) if energy_values else 0
    if total_steps_assigned:
        completion_rate = total_steps_completed / total_steps_assigned * 100
    else:
        completion_rate = 0

    # Получаем прогресс по цели
    goal_info = ""
    active_goal = await Goal.filter(user=user, status="active").first()
    if active_goal:
        stages = await active_goal.stages.all().order_by("order")
        current_stage = next((s for s in stages if s.status == "active"), None)

        # Вычисляем общий прогресс
        total_progress = 0
        for stage in stages:
            if stage.status == "completed":
                total_progress += 100
            elif stage.status == "active":
                total_progress += stage.progress
        overall_progress = total_progress // len(stages) if stages else 0

        goal_info = (
            f"\n🎯 *Цель:* {active_goal.title}\n"
            f"📍 Этап: {current_stage.title if current_stage else 'завершено'}\n"
            f"📈 Общий прогресс: {overall_progress}%\n"
            f"📅 До дедлайна: {(active_goal.deadline - today).days} дней\n"
        )

    # Формируем визуализацию недели
    week_visual = ""
    for i in range(7):
        day = week_ago + timedelta(days=i + 1)
        day_log = next((lg for lg in logs if lg.date == day), None)

        if day_log and day_log.completed_step_ids:
            icon = "🟢"
        elif day_log and day_log.assigned_step_ids:
            icon = "🟡"
        else:
            icon = "⚪"
        week_visual += f"{icon}"

    week_visual = f"[{week_visual}] Пн→Вс"

    # Streak info
    streak_text = ""
    if user.streak_days >= 7:
        streak_text = f"🔥 *{user.streak_days} дней подряд!* Ты горишь!"
    elif user.streak_days >= 3:
        streak_text = f"🔥 Streak: {user.streak_days} дней"
    elif user.streak_days > 0:
        streak_text = f"Streak: {user.streak_days}"

    # Мотивационное сообщение
    if completion_rate >= 80:
        motivation = "🏆 Отличная неделя! Ты машина!"
    elif completion_rate >= 50:
        motivation = "💪 Хорошая работа! Можно ещё лучше."
    elif completion_rate > 0:
        motivation = "🌱 Есть прогресс. Главное — не останавливаться."
    else:
        motivation = "Начни с малого — один шаг в день."

    await message.answer(
        f"📊 *Статистика за 7 дней*\n\n"
        f"{week_visual}\n\n"
        f"📅 Активных дней: {active_days}/7\n"
        f"✅ Выполнено шагов: {total_steps_completed}/{total_steps_assigned}\n"
        f"📈 Процент выполнения: {completion_rate:.0f}%\n"
        f"⚡ Средняя энергия: {avg_energy:.1f}/10\n"
        f"⭐ XP за неделю: +{total_xp}\n"
        f"{streak_text}\n"
        f"{goal_info}\n"
        f"{motivation}"
    )

    logger.info(
        f"Weekly report for user {user.telegram_id}: "
        f"{total_steps_completed}/{total_steps_assigned} steps"
    )
