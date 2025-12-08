# Правила работы с Tortoise ORM

Обязательные паттерны для работы с базой данных в проекте Antipanic Bot.

---

## 1. Определение моделей

### Базовый шаблон модели

```python
from tortoise import fields, models


class User(models.Model):
    """Пользователь бота."""
    
    id = fields.IntField(pk=True)
    telegram_id = fields.BigIntField(unique=True, index=True)
    username = fields.CharField(max_length=255, null=True)
    
    # Timestamps
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    # Reverse relations (для type hints)
    goals: fields.ReverseRelation["Goal"]

    class Meta:
        table = "users"

    def __str__(self) -> str:
        return f"User({self.telegram_id})"
```

### ForeignKey связи

```python
class Goal(models.Model):
    id = fields.IntField(pk=True)
    
    # ForeignKey с типизацией
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="goals",
        on_delete=fields.CASCADE
    )
    
    title = fields.CharField(max_length=255)
    
    # Reverse relation
    stages: fields.ReverseRelation["Stage"]

    class Meta:
        table = "goals"
```

### ManyToMany связи

```python
class Event(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    
    participants: fields.ManyToManyRelation["Team"] = fields.ManyToManyField(
        "models.Team",
        related_name="events",
        through="event_team"  # имя промежуточной таблицы
    )
```

---

## 2. Создание и обновление

### Создание объекта

```python
# Вариант 1: create()
user = await User.create(
    telegram_id=123456,
    username="john_doe"
)

# Вариант 2: save()
user = User(telegram_id=123456, username="john_doe")
await user.save()

# Создание с ForeignKey
goal = await Goal.create(
    user=user,  # передаём объект
    title="Выучить Python"
)

# Или через ID
goal = await Goal.create(
    user_id=user.id,  # передаём ID
    title="Выучить Python"
)
```

### Обновление

```python
# Изменение атрибутов + save
user.xp += 10
await user.save()

# Или update_fields для оптимизации
user.xp += 10
await user.save(update_fields=["xp"])

# Массовое обновление
await User.filter(level=1).update(level=2)
```

### get_or_create

```python
user, created = await User.get_or_create(
    telegram_id=123456,
    defaults={
        "username": "john_doe",
        "xp": 0
    }
)
if created:
    print("Новый пользователь создан")
```

---

## 3. Запросы (QuerySet)

### Базовые запросы

```python
# Получить один объект
user = await User.get(telegram_id=123456)

# Получить или None
user = await User.get_or_none(telegram_id=123456)

# Все записи
users = await User.all()

# Фильтрация
active_goals = await Goal.filter(status="active")

# Фильтрация + first
goal = await Goal.filter(user=user, status="active").first()
```

### Операторы фильтрации

```python
# Сравнение
await User.filter(xp__gt=100)       # >
await User.filter(xp__gte=100)      # >=
await User.filter(xp__lt=100)       # <
await User.filter(xp__lte=100)      # <=

# Строки
await Goal.filter(title__icontains="python")  # case-insensitive contains
await Goal.filter(title__startswith="Выучить")

# NULL
await User.filter(username__isnull=True)

# IN
await User.filter(level__in=[1, 2, 3])

# Диапазон
await DailyLog.filter(date__range=[start_date, end_date])
```

### Сортировка и лимиты

```python
# Сортировка
await User.all().order_by("-xp")  # DESC
await User.all().order_by("created_at")  # ASC

# Лимит и offset
await User.all().limit(10).offset(20)

# Первые N
top_users = await User.all().order_by("-xp").limit(10)
```

---

## 4. Связи и prefetch

### Доступ к связям

```python
# ForeignKey (ленивая загрузка)
goal = await Goal.get(id=1)
user = await goal.user  # отдельный запрос к БД

# Reverse ForeignKey
user = await User.get(id=1)
goals = await user.goals.all()

# Итерация по связям
async for goal in user.goals:
    print(goal.title)
```

### prefetch_related (N+1 проблема)

```python
# БЕЗ prefetch — N+1 запросов
goals = await Goal.all()
for goal in goals:
    user = await goal.user  # запрос на каждую итерацию!

# С prefetch — 2 запроса
goals = await Goal.all().prefetch_related("user")
for goal in goals:
    print(goal.user.username)  # уже загружено
```

### Многоуровневый prefetch

```python
# Загрузить goal → stages → steps
goals = await Goal.filter(user=user).prefetch_related(
    "stages",
    "stages__steps"
)

for goal in goals:
    for stage in goal.stages:
        for step in stage.steps:
            print(step.title)
```

### select_related (JOIN)

```python
# Для ForeignKey — один запрос с JOIN
goals = await Goal.all().select_related("user")
```

---

## 5. ManyToMany операции

```python
event = await Event.get(id=1)
team1 = await Team.get(id=1)
team2 = await Team.get(id=2)

# Добавить связи
await event.participants.add(team1, team2)

# Удалить связь
await event.participants.remove(team1)

# Очистить все связи
await event.participants.clear()

# Фильтрация через M2M
events = await Event.filter(participants__name="Team Alpha")
```

---

## 6. Фильтрация по связям

```python
# Фильтр по полю связанной модели
goals = await Goal.filter(user__telegram_id=123456)

# Глубокая фильтрация
steps = await Step.filter(
    stage__goal__user__telegram_id=123456,
    status="pending"
)

# Сортировка по связанному полю
goals = await Goal.filter(status="active").order_by("-user__xp")

# Distinct при фильтрации по M2M
events = await Event.filter(
    participants__name__in=["Team A", "Team B"]
).distinct()
```

---

## 7. Агрегации

```python
from tortoise.functions import Count, Sum, Avg, Max, Min

# Подсчёт
total = await User.all().count()

# Агрегация
from tortoise.functions import Sum
result = await Step.filter(status="completed").annotate(
    total_xp=Sum("xp_reward")
).values("total_xp")

# Группировка
from tortoise.functions import Count
stats = await Goal.all().annotate(
    stage_count=Count("stages")
).values("id", "title", "stage_count")
```

---

## 8. Транзакции

```python
from tortoise.transactions import in_transaction

async def complete_step(step_id: int, user_id: int):
    async with in_transaction():
        step = await Step.get(id=step_id)
        step.status = "completed"
        await step.save()

        user = await User.get(id=user_id)
        user.xp += step.xp_reward
        await user.save()
        # Если любая операция упадёт — откат всего
```

---

## 9. Инициализация

### Конфигурация

```python
# src/database/config.py
TORTOISE_ORM = {
    "connections": {
        "default": "sqlite://db.sqlite3"
    },
    "apps": {
        "models": {
            "models": ["src.database.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}
```

### Инициализация в main.py

```python
from tortoise import Tortoise
from src.database.config import TORTOISE_ORM

async def on_startup():
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()  # создаёт таблицы

async def on_shutdown():
    await Tortoise.close_connections()

# Регистрация в диспетчере
dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)
```

---

## 10. Антипаттерны

### ❌ N+1 запросы

```python
# ПЛОХО
goals = await Goal.all()
for goal in goals:
    user = await goal.user  # N запросов!

# ХОРОШО
goals = await Goal.all().prefetch_related("user")
```

### ❌ Синхронный доступ к связям без загрузки

```python
# ПЛОХО — AttributeError или пустой результат
goal = await Goal.get(id=1)
print(goal.user.username)  # user не загружен!

# ХОРОШО
goal = await Goal.get(id=1).prefetch_related("user")
print(goal.user.username)

# Или явная загрузка
goal = await Goal.get(id=1)
user = await goal.user
```

### ❌ Забыть await

```python
# ПЛОХО — получишь корутину, не данные
user = User.get(id=1)  # <coroutine object>

# ХОРОШО
user = await User.get(id=1)
```

---

## 11. Чеклист

- [ ] Модели имеют `class Meta` с явным `table`
- [ ] ForeignKey использует `ForeignKeyRelation` для типизации
- [ ] ReverseRelation указан для обратных связей
- [ ] Используется `prefetch_related` для избежания N+1
- [ ] Транзакции оборачивают связанные операции
- [ ] `await` перед всеми запросами к БД

