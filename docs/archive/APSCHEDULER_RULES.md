# Правила работы с APScheduler

Паттерны для интеграции планировщика задач в Antipanic Bot.

---

## 1. Инициализация AsyncScheduler

### Базовая настройка

```python
from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.local import LocalEventBroker

# Для локальной разработки — in-memory
scheduler = AsyncScheduler()

# Для production — с персистентным хранилищем
data_store = SQLAlchemyDataStore(engine)
event_broker = LocalEventBroker()
scheduler = AsyncScheduler(data_store=data_store, event_broker=event_broker)
```

### Интеграция с aiogram

```python
# src/scheduler.py
from apscheduler import AsyncScheduler

scheduler = AsyncScheduler()


async def setup_scheduler(bot: Bot):
    """Инициализация планировщика."""
    # Добавляем bot в контекст для использования в задачах
    scheduler.configure(job_defaults={"bot": bot})


async def start_scheduler():
    """Запуск планировщика."""
    await scheduler.start_in_background()


async def stop_scheduler():
    """Остановка планировщика."""
    await scheduler.stop()
```

```python
# src/main.py
from src.scheduler import scheduler, setup_scheduler, start_scheduler, stop_scheduler

async def on_startup(bot: Bot):
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    await setup_scheduler(bot)
    await start_scheduler()

async def on_shutdown():
    await stop_scheduler()
    await Tortoise.close_connections()
```

---

## 2. Триггеры

### CronTrigger (расписание)

```python
from apscheduler.triggers.cron import CronTrigger

# Каждый день в 9:00
trigger = CronTrigger(hour=9, minute=0)

# Каждый день в 21:00
trigger = CronTrigger(hour=21, minute=0)

# Каждый понедельник в 10:00
trigger = CronTrigger(day_of_week="mon", hour=10, minute=0)

# Каждые 30 минут
trigger = CronTrigger(minute="*/30")
```

### IntervalTrigger (интервал)

```python
from apscheduler.triggers.interval import IntervalTrigger
from datetime import timedelta

# Каждые 5 минут
trigger = IntervalTrigger(minutes=5)

# Каждый час
trigger = IntervalTrigger(hours=1)

# Каждые 30 секунд
trigger = IntervalTrigger(seconds=30)
```

### DateTrigger (одноразовый)

```python
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta

# Через 10 минут
run_at = datetime.now() + timedelta(minutes=10)
trigger = DateTrigger(run_date=run_at)

# В конкретное время
trigger = DateTrigger(run_date=datetime(2024, 12, 31, 23, 59))
```

---

## 3. Добавление задач (schedules)

### Добавление schedule

```python
from apscheduler.triggers.cron import CronTrigger

async def send_morning_reminder(user_id: int, bot: Bot):
    """Задача утреннего напоминания."""
    await bot.send_message(
        chat_id=user_id,
        text="🌅 Доброе утро! Как твоя энергия сегодня?"
    )


# Добавление расписания
schedule_id = await scheduler.add_schedule(
    send_morning_reminder,
    trigger=CronTrigger(hour=9, minute=0),
    id=f"morning_{user_id}",  # уникальный ID
    args=[user_id],
    kwargs={"bot": bot},
)
```

### Динамическое расписание для пользователя

```python
async def schedule_user_reminders(user: User, bot: Bot):
    """Настройка напоминаний для пользователя."""
    
    # Парсим время из настроек
    morning_hour, morning_minute = map(int, user.reminder_morning.split(":"))
    evening_hour, evening_minute = map(int, user.reminder_evening.split(":"))
    
    # Утреннее напоминание
    await scheduler.add_schedule(
        send_morning_reminder,
        trigger=CronTrigger(hour=morning_hour, minute=morning_minute),
        id=f"morning_{user.telegram_id}",
        args=[user.telegram_id],
        kwargs={"bot": bot},
        conflict_policy=ConflictPolicy.replace,  # перезаписать если есть
    )
    
    # Вечернее напоминание
    await scheduler.add_schedule(
        send_evening_reminder,
        trigger=CronTrigger(hour=evening_hour, minute=evening_minute),
        id=f"evening_{user.telegram_id}",
        args=[user.telegram_id],
        kwargs={"bot": bot},
        conflict_policy=ConflictPolicy.replace,
    )
```

---

## 4. Управление schedules

### Получение schedule

```python
# По ID
schedule = await scheduler.get_schedule(f"morning_{user_id}")

# Все schedules
schedules = await scheduler.get_schedules()
```

### Пауза и возобновление

```python
# Пауза
await scheduler.pause_schedule(f"morning_{user_id}")

# Возобновление
await scheduler.unpause_schedule(f"morning_{user_id}")

# Возобновление с указанием времени
await scheduler.unpause_schedule(
    f"morning_{user_id}",
    resume_from="now"  # или datetime
)
```

### Удаление schedule

```python
await scheduler.remove_schedule(f"morning_{user_id}")
```

---

## 5. Одноразовые задачи (jobs)

### Немедленное выполнение

```python
# Добавить job для немедленного выполнения
job_id = await scheduler.add_job(
    send_notification,
    args=[user_id, "Напоминание!"],
    kwargs={"bot": bot},
)
```

### Отложенное выполнение

```python
from datetime import datetime, timedelta

# Через 5 минут
run_at = datetime.now() + timedelta(minutes=5)

job_id = await scheduler.add_job(
    send_delayed_reminder,
    trigger=DateTrigger(run_date=run_at),
    args=[user_id, "Не забудь про шаг!"],
)
```

### Выполнение и ожидание результата

```python
# Запустить job и дождаться результата
result = await scheduler.run_job(
    my_task_function,
    args=[arg1, arg2],
)
print(f"Результат: {result}")
```

---

## 6. События и подписки

### Подписка на события

```python
from apscheduler import Event, JobAcquired, JobReleased, ScheduleAdded

async def job_listener(event: Event):
    """Слушатель событий планировщика."""
    if isinstance(event, JobAcquired):
        logger.info(f"Job acquired: {event.job_id}")
    elif isinstance(event, JobReleased):
        logger.info(f"Job released: {event.job_id}, outcome: {event.outcome}")

# Подписка
scheduler.subscribe(job_listener, {JobAcquired, JobReleased})
```

### Логирование выполнения задач

```python
from apscheduler import JobReleased, JobOutcome

async def log_job_results(event: JobReleased):
    if event.outcome == JobOutcome.success:
        logger.info(f"Job {event.job_id} completed successfully")
    elif event.outcome == JobOutcome.error:
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    elif event.outcome == JobOutcome.missed_start_deadline:
        logger.warning(f"Job {event.job_id} missed deadline")

scheduler.subscribe(log_job_results, {JobReleased})
```

---

## 7. Структура модуля scheduler

```python
# src/services/scheduler.py
import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler import ConflictPolicy

from src.database.models import User

logger = logging.getLogger(__name__)

scheduler = AsyncScheduler()
_bot: Optional[Bot] = None


def set_bot(bot: Bot):
    """Установить инстанс бота для использования в задачах."""
    global _bot
    _bot = bot


def get_bot() -> Bot:
    """Получить инстанс бота."""
    if _bot is None:
        raise RuntimeError("Bot not initialized in scheduler")
    return _bot


# === Задачи ===

async def send_morning_reminder(user_id: int):
    """Утреннее напоминание."""
    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=user_id,
            text="🌅 Доброе утро! Как твоя энергия сегодня?\n\nНапиши /morning"
        )
        logger.info(f"Morning reminder sent to {user_id}")
    except Exception as e:
        logger.error(f"Failed to send morning reminder to {user_id}: {e}")


async def send_evening_reminder(user_id: int):
    """Вечернее напоминание."""
    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=user_id,
            text="🌙 Как прошёл день? Давай подведём итоги.\n\nНапиши /evening"
        )
        logger.info(f"Evening reminder sent to {user_id}")
    except Exception as e:
        logger.error(f"Failed to send evening reminder to {user_id}: {e}")


# === API для управления напоминаниями ===

async def setup_user_reminders(user: User):
    """Настроить напоминания для пользователя."""
    morning_h, morning_m = map(int, user.reminder_morning.split(":"))
    evening_h, evening_m = map(int, user.reminder_evening.split(":"))

    await scheduler.add_schedule(
        send_morning_reminder,
        trigger=CronTrigger(hour=morning_h, minute=morning_m),
        id=f"morning_{user.telegram_id}",
        args=[user.telegram_id],
        conflict_policy=ConflictPolicy.replace,
    )

    await scheduler.add_schedule(
        send_evening_reminder,
        trigger=CronTrigger(hour=evening_h, minute=evening_m),
        id=f"evening_{user.telegram_id}",
        args=[user.telegram_id],
        conflict_policy=ConflictPolicy.replace,
    )

    logger.info(f"Reminders set for user {user.telegram_id}")


async def pause_user_reminders(user_id: int):
    """Приостановить напоминания."""
    try:
        await scheduler.pause_schedule(f"morning_{user_id}")
        await scheduler.pause_schedule(f"evening_{user_id}")
    except Exception as e:
        logger.warning(f"Could not pause reminders for {user_id}: {e}")


async def remove_user_reminders(user_id: int):
    """Удалить напоминания пользователя."""
    try:
        await scheduler.remove_schedule(f"morning_{user_id}")
        await scheduler.remove_schedule(f"evening_{user_id}")
    except Exception as e:
        logger.warning(f"Could not remove reminders for {user_id}: {e}")


# === Lifecycle ===

async def start():
    """Запустить планировщик."""
    await scheduler.start_in_background()
    logger.info("Scheduler started")


async def stop():
    """Остановить планировщик."""
    await scheduler.stop()
    logger.info("Scheduler stopped")
```

---

## 8. Интеграция в main.py

```python
# src/main.py
from src.services import scheduler as scheduler_service

async def on_startup(bot: Bot):
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    
    # Инициализация планировщика
    scheduler_service.set_bot(bot)
    await scheduler_service.start()
    
    logger.info("Bot started")


async def on_shutdown():
    await scheduler_service.stop()
    await Tortoise.close_connections()
    logger.info("Bot stopped")


async def main():
    bot = Bot(token=config.BOT_TOKEN.get_secret_value())
    dp = Dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # ... include routers ...

    await dp.start_polling(bot)
```

---

## 9. Антипаттерны

### ❌ Синхронный планировщик

```python
# ПЛОХО — блокирует event loop
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()

# ХОРОШО
from apscheduler import AsyncScheduler
scheduler = AsyncScheduler()
```

### ❌ Забыть conflict_policy

```python
# ПЛОХО — ошибка при повторном добавлении
await scheduler.add_schedule(task, trigger, id="my_task")
await scheduler.add_schedule(task, trigger, id="my_task")  # ConflictError!

# ХОРОШО
await scheduler.add_schedule(
    task, trigger, id="my_task",
    conflict_policy=ConflictPolicy.replace
)
```

### ❌ Не обрабатывать ошибки в задачах

```python
# ПЛОХО — ошибка убьёт задачу молча
async def my_task(user_id: int):
    await bot.send_message(user_id, "Hello")

# ХОРОШО
async def my_task(user_id: int):
    try:
        await bot.send_message(user_id, "Hello")
    except Exception as e:
        logger.error(f"Task failed for {user_id}: {e}")
```

---

## 10. Чеклист

- [ ] Используется `AsyncScheduler`
- [ ] Планировщик запускается в `on_startup`, останавливается в `on_shutdown`
- [ ] Bot передаётся в задачи через глобальный getter или kwargs
- [ ] `conflict_policy` указан для schedules с фиксированным ID
- [ ] Ошибки в задачах логируются и не роняют планировщик
- [ ] ID schedules содержат user_id для уникальности

