# Tortoise ORM (Quick Reference)

## Модели

```python
from tortoise import fields, models

class User(models.Model):
    id = fields.IntField(pk=True)
    telegram_id = fields.BigIntField(unique=True, index=True)
    username = fields.CharField(max_length=255, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    # Reverse relations (type hints)
    goals: fields.ReverseRelation["Goal"]
    
    class Meta:
        table = "users"

class Goal(models.Model):
    id = fields.IntField(pk=True)
    
    # ForeignKey с типизацией
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User",
        related_name="goals",
        on_delete=fields.CASCADE
    )
    
    title = fields.CharField(max_length=255)
    stages: fields.ReverseRelation["Stage"]
    
    class Meta:
        table = "goals"
```

## Создание и обновление

```python
# Создание
user = await User.create(telegram_id=123456, username="john")
goal = await Goal.create(user=user, title="Learn Python")

# get_or_create
user, created = await User.get_or_create(
    telegram_id=123456,
    defaults={"username": "john", "xp": 0}
)

# Обновление
user.xp += 10
await user.save()
# Или только определённые поля:
await user.save(update_fields=["xp"])

# Массовое обновление
await User.filter(level=1).update(level=2)
```

## Запросы

```python
# Получить один
user = await User.get(telegram_id=123456)

# Получить или None (ВСЕГДА используй это!)
user = await User.get_or_none(telegram_id=123456)
if not user:
    return

# Все записи
users = await User.all()

# Фильтрация
active_goals = await Goal.filter(status="active")
goal = await Goal.filter(user=user, status="active").first()

# Операторы
await User.filter(xp__gt=100)              # >
await User.filter(xp__gte=100)             # >=
await Goal.filter(title__icontains="py")   # contains (case-insensitive)
await User.filter(level__in=[1, 2, 3])     # IN

# Сортировка и лимиты
await User.all().order_by("-xp")           # DESC
await User.all().order_by("created_at")    # ASC
await User.all().limit(10).offset(20)
```

## prefetch_related (КРИТИЧНО!)

```python
# ❌ ПЛОХО — N+1 запросов
goals = await Goal.all()
for goal in goals:
    user = await goal.user  # запрос на каждой итерации!

# ✅ ХОРОШО — 2 запроса
goals = await Goal.all().prefetch_related("user")
for goal in goals:
    print(goal.user.username)  # уже загружено

# Многоуровневый prefetch
goals = await Goal.filter(user=user).prefetch_related(
    "stages",
    "stages__steps"
)
for goal in goals:
    for stage in goal.stages:
        for step in stage.steps:
            print(step.title)
```

## Фильтрация по связям

```python
# По полю связанной модели
goals = await Goal.filter(user__telegram_id=123456)

# Глубокая фильтрация
steps = await Step.filter(
    stage__goal__user__telegram_id=123456,
    status="pending"
)
```

## Транзакции

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

## Инициализация

```python
# src/database/config.py
TORTOISE_ORM = {
    "connections": {"default": "sqlite://db.sqlite3"},
    "apps": {
        "models": {
            "models": ["src.database.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}

# src/main.py
from tortoise import Tortoise

async def on_startup():
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()

async def on_shutdown():
    await Tortoise.close_connections()

dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)
```

## Антипаттерны

```python
# ❌ Забыть await
user = User.get(id=1)  # <coroutine>, не данные!

# ✅ Правильно
user = await User.get(id=1)

# ❌ Доступ к связи без prefetch
goal = await Goal.get(id=1)
print(goal.user.username)  # AttributeError!

# ✅ Правильно
goal = await Goal.get(id=1).prefetch_related("user")
print(goal.user.username)
```

## Чеклист

- [ ] `await` перед ВСЕМИ запросами к БД
- [ ] `prefetch_related` для избежания N+1
- [ ] `get_or_none` вместо `get` (когда объект может не существовать)
- [ ] `ForeignKeyRelation` для type hints
- [ ] Транзакции для связанных операций
