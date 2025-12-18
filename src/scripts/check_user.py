"""
Проверка данных пользователя в БД.
"""

import asyncio
import sys

from tortoise import Tortoise

from src.database.config import TORTOISE_ORM
from src.database.models import DailyLog, Goal, Stage, Step, User


async def check_user(telegram_id: int):
    await Tortoise.init(config=TORTOISE_ORM)

    try:
        user = await User.get_or_none(telegram_id=telegram_id)

        if not user:
            print(f"❌ Пользователь {telegram_id} не найден.")
            return

        print(f"👤 User: {user.first_name} (@{user.username})")
        print(f"   ID: {user.id}, XP: {user.xp}, Level: {user.level}")

        # Goals
        goals = await Goal.filter(user=user).prefetch_related("stages__steps")
        print(f"\n🎯 Goals: {len(goals)}")
        for goal in goals:
            # AICODE-NOTE: Используем prefetch_related данные вместо повторных запросов
            stages = goal.stages
            steps_count = sum(len(s.steps) for s in stages)
            print(f"   - {goal.title} (status={goal.status}, stages={len(stages)}, steps={steps_count})")

        # DailyLogs
        logs = await DailyLog.filter(user=user)
        print(f"\n📊 DailyLogs: {len(logs)}")

    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    telegram_id = int(sys.argv[1]) if len(sys.argv) > 1 else 579067869
    asyncio.run(check_user(telegram_id))

