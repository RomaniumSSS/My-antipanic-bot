"""
Скрипт для полного удаления пользователя из базы данных.

Использование:
    python -m src.scripts.delete_user <telegram_id>

Пример:
    python -m src.scripts.delete_user 123456789

ВНИМАНИЕ: Удаление необратимо! Будут удалены:
- User
- Все Goals (и связанные Stages, Steps)
- Все DailyLogs
"""

import asyncio
import sys

from tortoise import Tortoise

from src.database.config import TORTOISE_ORM
from src.database.models import DailyLog, Goal, User


async def delete_user_by_telegram_id(telegram_id: int) -> None:
    """
    Удаляет пользователя и все связанные данные.

    Args:
        telegram_id: Telegram ID пользователя
    """
    await Tortoise.init(config=TORTOISE_ORM)

    try:
        # Найти пользователя
        user = await User.get_or_none(telegram_id=telegram_id)

        if not user:
            print(f"❌ Пользователь с telegram_id={telegram_id} не найден.")
            return

        print(f"👤 Найден пользователь: {user.first_name} (@{user.username})")
        print(f"   ID: {user.id}, XP: {user.xp}, Level: {user.level}")

        # Статистика перед удалением
        goals_count = await Goal.filter(user=user).count()
        logs_count = await DailyLog.filter(user=user).count()

        print("\n📊 Будет удалено:")
        print("   - 1 User")
        print(f"   - {goals_count} Goals (+ все Stages и Steps)")
        print(f"   - {logs_count} DailyLogs")

        # Подтверждение (если запущено интерактивно)
        if sys.stdin.isatty():
            confirm = input(f"\n⚠️ Удалить пользователя {telegram_id}? (yes/no): ")
            if confirm.lower() != "yes":
                print("❌ Удаление отменено.")
                return

        # Удаление (CASCADE удалит все связанные записи)
        await user.delete()

        print(f"\n✅ Пользователь {telegram_id} и все связанные данные удалены.")

    finally:
        await Tortoise.close_connections()


async def main():
    if len(sys.argv) < 2:
        print("❌ Использование: python -m src.scripts.delete_user <telegram_id>")
        print("   Пример: python -m src.scripts.delete_user 123456789")
        sys.exit(1)

    try:
        telegram_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Неверный telegram_id: {sys.argv[1]} (должно быть число)")
        sys.exit(1)

    await delete_user_by_telegram_id(telegram_id)


if __name__ == "__main__":
    asyncio.run(main())

