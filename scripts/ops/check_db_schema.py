"""
Скрипт для проверки синхронизации схемы БД с моделями в production.

Usage:
    python -m scripts.ops.check_db_schema

AICODE-NOTE: Этот скрипт помогает диагностировать проблемы с миграциями
до того, как они приведут к падению бота в production.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tortoise import Tortoise

from src.database.config import TORTOISE_ORM
from src.database.models import DailyLog, Goal, Stage, Step, User


async def check_table_exists(model, table_name: str) -> tuple[bool, str]:
    """Проверяет существование таблицы и доступность всех колонок."""
    try:
        await model.all().limit(1)
        return True, f"✅ Table '{table_name}' exists and is accessible"
    except Exception as e:
        return False, f"❌ Table '{table_name}' error: {e}"


async def check_daily_log_columns() -> tuple[bool, str]:
    """Проверяет критичные колонки DailyLog (morning_calls_count, stuck_calls_count)."""
    try:
        # Пытаемся сделать запрос с явным выбором этих колонок
        result = await DailyLog.all().limit(1).values(
            "id",
            "morning_calls_count",
            "stuck_calls_count",
        )
        return True, "✅ Rate limit columns (morning_calls_count, stuck_calls_count) exist"
    except Exception as e:
        return False, f"❌ Rate limit columns error: {e}"


async def check_user_reminder_columns() -> tuple[bool, str]:
    """Проверяет колонки для напоминаний в User."""
    try:
        result = await User.all().limit(1).values(
            "id",
            "next_morning_reminder_at",
            "next_evening_reminder_at",
            "reminders_enabled",
        )
        return True, "✅ Reminder columns exist"
    except Exception as e:
        return False, f"❌ Reminder columns error: {e}"


async def check_relationships() -> tuple[bool, str]:
    """Проверяет работу связей между моделями."""
    try:
        # Создаём тестовую структуру (будет откачена, если транзакция поддерживается)
        test_user = await User.create(
            telegram_id=999_999_999_999,  # Явно недействительный ID
            username="__schema_check_test__",
            first_name="Test",
        )
        
        test_goal = await Goal.create(
            user=test_user,
            title="__test__",
            start_date=date.today(),
            deadline=date.today(),
        )
        
        test_stage = await Stage.create(
            goal=test_goal,
            title="__test__",
            order=1,
            start_date=date.today(),
            end_date=date.today(),
        )
        
        test_step = await Step.create(
            stage=test_stage,
            title="__test__",
            scheduled_date=date.today(),
            xp_reward=1,
        )
        
        # Проверяем prefetch_related
        fetched_goal = await Goal.get(id=test_goal.id).prefetch_related("stages__steps")
        assert len(fetched_goal.stages) == 1
        assert len(fetched_goal.stages[0].steps) == 1
        
        # Удаляем тестовые данные
        await test_step.delete()
        await test_stage.delete()
        await test_goal.delete()
        await test_user.delete()
        
        return True, "✅ Relationships (ForeignKey, prefetch_related) work correctly"
    except Exception as e:
        return False, f"❌ Relationships error: {e}"


async def main():
    """Основная функция проверки схемы БД."""
    print("🔍 Checking database schema synchronization...")
    print("=" * 60)
    
    await Tortoise.init(config=TORTOISE_ORM)
    
    checks = [
        ("Users table", check_table_exists(User, "users")),
        ("Goals table", check_table_exists(Goal, "goals")),
        ("Stages table", check_table_exists(Stage, "stages")),
        ("Steps table", check_table_exists(Step, "steps")),
        ("DailyLogs table", check_table_exists(DailyLog, "daily_logs")),
        ("DailyLog rate limit columns", check_daily_log_columns()),
        ("User reminder columns", check_user_reminder_columns()),
        ("Model relationships", check_relationships()),
    ]
    
    all_passed = True
    
    for check_name, check_coro in checks:
        success, message = await check_coro
        print(f"\n{check_name}:")
        print(f"  {message}")
        if not success:
            all_passed = False
    
    await Tortoise.close_connections()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All checks passed! Database schema is synchronized.")
        return 0
    else:
        print("❌ Some checks failed. Database schema is NOT synchronized.")
        print("\n💡 Possible solutions:")
        print("  1. Run migrations: aerich upgrade")
        print("  2. Check if migrations are up to date: aerich history")
        print("  3. Create missing migration: aerich migrate --name 'fix_schema'")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

