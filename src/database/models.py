"""
Модели базы данных для Antipanic Bot.

Структура:
- User: пользователь с настройками и статистикой
- Goal: цель с дедлайном
- Stage: этап цели
- Step: конкретный шаг (задача)
- DailyLog: дневник дня (энергия, состояние, что сделано)
"""

from tortoise import fields, models


class User(models.Model):
    """Пользователь бота."""

    id = fields.IntField(primary_key=True)
    telegram_id = fields.BigIntField(unique=True, db_index=True)
    username = fields.CharField(max_length=255, null=True)
    first_name = fields.CharField(max_length=255, null=True)

    # Статистика
    xp = fields.IntField(default=0)
    level = fields.IntField(default=1)
    streak_days = fields.IntField(default=0)
    streak_last_date = fields.DateField(null=True)

    # Настройки напоминаний (время в формате HH:MM, в часовом поясе пользователя)
    reminder_morning = fields.CharField(max_length=5, default="09:00")
    reminder_evening = fields.CharField(max_length=5, default="21:00")
    timezone_offset = fields.IntField(default=3)  # UTC+3 (Moscow)
    reminders_enabled = fields.BooleanField(default=True)

    # Следующие напоминания (UTC datetime для cron)
    next_morning_reminder_at = fields.DatetimeField(null=True)
    next_evening_reminder_at = fields.DatetimeField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)

    goals: fields.ReverseRelation["Goal"]
    daily_logs: fields.ReverseRelation["DailyLog"]

    class Meta:
        table = "users"


class Goal(models.Model):
    """Цель пользователя."""

    id = fields.IntField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="goals", on_delete=fields.CASCADE
    )
    user_id: int  # AICODE-NOTE: MyPy hint for FK (Tortoise auto-creates this)

    title = fields.CharField(max_length=255)
    description = fields.TextField(null=True)

    # Даты
    start_date = fields.DateField(auto_now_add=True)
    deadline = fields.DateField()

    # Статус: active, completed, paused, abandoned
    status = fields.CharField(max_length=20, default="active")

    created_at = fields.DatetimeField(auto_now_add=True)

    stages: fields.ReverseRelation["Stage"]

    class Meta:
        table = "goals"


class Stage(models.Model):
    """Этап цели (2-4 этапа на цель)."""

    id = fields.IntField(primary_key=True)
    goal: fields.ForeignKeyRelation[Goal] = fields.ForeignKeyField(
        "models.Goal", related_name="stages", on_delete=fields.CASCADE
    )

    title = fields.CharField(max_length=255)
    order = fields.IntField(default=0)  # Порядок этапа (1, 2, 3...)

    # Даты этапа
    start_date = fields.DateField()
    end_date = fields.DateField()

    # Прогресс (0-100)
    progress = fields.IntField(default=0)

    # Статус: pending, active, completed
    status = fields.CharField(max_length=20, default="pending")

    steps: fields.ReverseRelation["Step"]

    class Meta:
        table = "stages"


class Step(models.Model):
    """
    Конкретный шаг/задача.
    Привязан к этапу и имеет градацию сложности.
    """

    id = fields.IntField(primary_key=True)
    stage: fields.ForeignKeyRelation[Stage] = fields.ForeignKeyField(
        "models.Stage", related_name="steps", on_delete=fields.CASCADE
    )

    title = fields.CharField(max_length=500)

    # Сложность: easy (5-10 мин), medium (15-30 мин), hard (45-90 мин)
    difficulty = fields.CharField(max_length=10, default="medium")

    # Оценка времени в минутах
    estimated_minutes = fields.IntField(default=15)

    # XP за выполнение
    xp_reward = fields.IntField(default=20)

    # Запланированная дата (может быть null = не запланировано)
    scheduled_date = fields.DateField(null=True)

    # Статус: pending, completed, skipped
    status = fields.CharField(max_length=20, default="pending")
    completed_at = fields.DatetimeField(null=True)

    class Meta:
        table = "steps"


class DailyLog(models.Model):
    """
    Дневник дня.
    Хранит состояние пользователя и результаты дня.
    """

    id = fields.IntField(primary_key=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="daily_logs", on_delete=fields.CASCADE
    )

    date = fields.DateField()

    # Утренний чек-ин
    energy_level = fields.IntField(null=True)  # 1-10
    mood_text = fields.CharField(max_length=100, null=True)  # "тревожно", "бодро"

    # Назначенные шаги (JSON: список ID шагов)
    assigned_step_ids: list[int] = fields.JSONField(default=[])

    # Выполненные шаги (JSON: список ID шагов)
    completed_step_ids: list[int] = fields.JSONField(default=[])

    # Причины пропуска (JSON: {"step_id": "причина"})
    skip_reasons: dict[str, str] = fields.JSONField(default={})

    # Вечерняя оценка дня (1-5 или emoji)
    day_rating = fields.CharField(max_length=20, null=True)

    # XP заработанный за день
    xp_earned = fields.IntField(default=0)

    # Rate limiting для AI вызовов (Plan 005)
    morning_calls_count = fields.IntField(default=0)  # Вызовы /morning за день
    stuck_calls_count = fields.IntField(default=0)  # Вызовы /stuck за день

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "daily_logs"
        unique_together = (("user", "date"),)
