"""
Тесты для проверки синхронизации схемы БД с моделями Tortoise ORM.

AICODE-NOTE: Эти тесты помогают обнаружить проблемы с миграциями и несоответствия
между моделями и реальной схемой БД. Критично для предотвращения OperationalError.
"""

import pytest
from tortoise import Tortoise
from tortoise.exceptions import OperationalError

from src.database.models import DailyLog, Goal, Stage, Step, User


@pytest.mark.asyncio
async def test_all_models_have_tables(db):
    """Проверяем, что все модели создали таблицы в БД."""
    connection = Tortoise.get_connection("default")
    
    # Проверяем существование таблиц
    tables = {
        "users": User,
        "goals": Goal,
        "stages": Stage,
        "steps": Step,
        "daily_logs": DailyLog,
    }
    
    for table_name, model in tables.items():
        # Пытаемся сделать простой запрос - если таблица не существует, будет ошибка
        try:
            await model.all().limit(1)
        except OperationalError as e:
            pytest.fail(f"Table '{table_name}' does not exist or has schema issues: {e}")


@pytest.mark.asyncio
async def test_daily_log_rate_limit_columns_exist(db):
    """
    Проверяем, что колонки morning_calls_count и stuck_calls_count существуют в DailyLog.
    
    AICODE-NOTE: Регрессионный тест для проблемы с отсутствующими колонками
    (OperationalError: column "morning_calls_count" does not exist).
    """
    # Создаём тестового пользователя
    user = await User.create(
        telegram_id=123456789,
        username="test_user",
        first_name="Test",
    )
    
    # Создаём DailyLog с rate limit полями
    from datetime import date
    
    daily_log = await DailyLog.create(
        user=user,
        date=date.today(),
        morning_calls_count=3,
        stuck_calls_count=5,
    )
    
    # Проверяем, что можем прочитать эти поля
    fetched_log = await DailyLog.get(id=daily_log.id)
    assert fetched_log.morning_calls_count == 3
    assert fetched_log.stuck_calls_count == 5
    
    # Проверяем, что можем обновить эти поля
    fetched_log.morning_calls_count += 1
    await fetched_log.save()
    
    reloaded = await DailyLog.get(id=daily_log.id)
    assert reloaded.morning_calls_count == 4


@pytest.mark.asyncio
async def test_daily_log_all_fields_accessible(db):
    """Проверяем, что все поля DailyLog доступны для чтения/записи."""
    from datetime import date
    
    user = await User.create(
        telegram_id=987654321,
        username="test_user2",
        first_name="Test2",
    )
    
    # Создаём DailyLog со всеми полями
    daily_log = await DailyLog.create(
        user=user,
        date=date.today(),
        energy_level=7,
        mood_text="хорошо",
        assigned_step_ids=[1, 2, 3],
        completed_step_ids=[1],
        skip_reasons={"2": "не было времени"},
        day_rating="5",
        xp_earned=50,
        morning_calls_count=2,
        stuck_calls_count=1,
    )
    
    # Проверяем, что можем прочитать все поля
    fetched = await DailyLog.get(id=daily_log.id)
    assert fetched.energy_level == 7
    assert fetched.mood_text == "хорошо"
    assert fetched.assigned_step_ids == [1, 2, 3]
    assert fetched.completed_step_ids == [1]
    assert fetched.skip_reasons == {"2": "не было времени"}
    assert fetched.day_rating == "5"
    assert fetched.xp_earned == 50
    assert fetched.morning_calls_count == 2
    assert fetched.stuck_calls_count == 1


@pytest.mark.asyncio
async def test_daily_log_rate_limit_defaults(db):
    """Проверяем, что rate limit поля имеют правильные значения по умолчанию."""
    from datetime import date
    
    user = await User.create(
        telegram_id=111222333,
        username="test_user3",
        first_name="Test3",
    )
    
    # Создаём DailyLog без указания rate limit полей
    daily_log = await DailyLog.create(
        user=user,
        date=date.today(),
    )
    
    # Проверяем, что значения по умолчанию = 0
    assert daily_log.morning_calls_count == 0
    assert daily_log.stuck_calls_count == 0


@pytest.mark.asyncio
async def test_user_model_all_fields(db):
    """Проверяем, что все поля User доступны."""
    from datetime import date, datetime
    
    user = await User.create(
        telegram_id=555666777,
        username="full_user",
        first_name="Full",
        xp=100,
        level=2,
        streak_days=5,
        streak_last_date=date.today(),
        reminder_morning="08:00",
        reminder_evening="22:00",
        timezone_offset=3,
        reminders_enabled=True,
    )
    
    fetched = await User.get(telegram_id=555666777)
    assert fetched.username == "full_user"
    assert fetched.first_name == "Full"
    assert fetched.xp == 100
    assert fetched.level == 2
    assert fetched.streak_days == 5
    assert fetched.reminder_morning == "08:00"
    assert fetched.reminder_evening == "22:00"
    assert fetched.timezone_offset == 3
    assert fetched.reminders_enabled is True


@pytest.mark.asyncio
async def test_goal_stage_step_relationships(db):
    """Проверяем, что связи между Goal, Stage, Step работают корректно."""
    from datetime import date, timedelta
    
    user = await User.create(
        telegram_id=888999000,
        username="rel_user",
        first_name="Relations",
    )
    
    goal = await Goal.create(
        user=user,
        title="Тестовая цель",
        start_date=date.today(),
        deadline=date.today() + timedelta(days=30),
    )
    
    stage = await Stage.create(
        goal=goal,
        title="Первый этап",
        order=1,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=10),
    )
    
    step = await Step.create(
        stage=stage,
        title="Тестовый шаг",
        scheduled_date=date.today(),
        xp_reward=10,
    )
    
    # Проверяем обратные связи
    fetched_goal = await Goal.get(id=goal.id).prefetch_related("stages")
    assert len(fetched_goal.stages) == 1
    
    fetched_stage = await Stage.get(id=stage.id).prefetch_related("steps")
    assert len(fetched_stage.steps) == 1
    
    # Проверяем доступ через связи
    fetched_step = await Step.get(id=step.id).prefetch_related("stage__goal")
    assert fetched_step.stage.goal.title == "Тестовая цель"


@pytest.mark.asyncio
async def test_daily_log_get_or_none_works(db):
    """
    Тест для проверки, что get_or_none работает корректно с DailyLog.
    
    AICODE-NOTE: Регрессионный тест — именно этот запрос падал
    в cmd_evening и cmd_morning с OperationalError.
    """
    from datetime import date
    
    user = await User.create(
        telegram_id=444555666,
        username="getornone_user",
        first_name="GetOrNone",
    )
    
    today = date.today()
    
    # Первый вызов — должен вернуть None
    daily_log = await DailyLog.get_or_none(user=user, date=today)
    assert daily_log is None
    
    # Создаём запись
    await DailyLog.create(
        user=user,
        date=today,
        morning_calls_count=1,
    )
    
    # Второй вызов — должен вернуть объект
    daily_log = await DailyLog.get_or_none(user=user, date=today)
    assert daily_log is not None
    assert daily_log.morning_calls_count == 1


@pytest.mark.asyncio
async def test_daily_log_unique_constraint(db):
    """Проверяем, что нельзя создать два DailyLog для одного пользователя и даты."""
    from datetime import date
    from tortoise.exceptions import IntegrityError
    
    user = await User.create(
        telegram_id=777888999,
        username="unique_user",
        first_name="Unique",
    )
    
    today = date.today()
    
    # Первая запись
    await DailyLog.create(user=user, date=today)
    
    # Вторая запись с той же датой должна упасть
    with pytest.raises(IntegrityError):
        await DailyLog.create(user=user, date=today)

