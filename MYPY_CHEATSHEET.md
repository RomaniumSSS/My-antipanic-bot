# mypy — Шпаргалка для быстрого старта

## 🚀 Команды

```bash
# Проверить весь проект
mypy src/

# Проверить конкретный модуль
mypy src/services/

# Проверить один файл
mypy src/services/ai.py

# Показать коды ошибок
mypy src/ --show-error-codes

# Игнорировать отсутствующие импорты
mypy src/ --ignore-missing-imports
```

---

## 📝 Базовая типизация

```python
# Простые типы
def greet(name: str) -> str:
    return f"Hello, {name}"

# Множественные аргументы
def add(a: int, b: int) -> int:
    return a + b

# Optional (может быть None)
def find_user(user_id: int) -> User | None:
    return await User.get_or_none(id=user_id)

# List, Dict
def get_ids() -> list[int]:
    return [1, 2, 3]

def get_mapping() -> dict[str, int]:
    return {"a": 1, "b": 2}
```

---

## 🔧 Tortoise ORM

```python
from tortoise import fields, models

class User(models.Model):
    # ForeignKey
    goal: fields.ForeignKeyRelation[Goal] = fields.ForeignKeyField(
        "models.Goal", related_name="users"
    )
    
    # Reverse relation
    steps: fields.ReverseRelation["Step"]
    
    # JSON поля
    settings: dict[str, str] = fields.JSONField(default={})
    tags: list[str] = fields.JSONField(default=[])
```

---

## ⚠️ Частые ошибки

### 1. Забыли return type

```python
# ❌ BAD
async def get_user(id: int):
    return await User.get(id=id)

# ✅ GOOD
async def get_user(id: int) -> User:
    return await User.get(id=id)
```

### 2. Не проверили на None

```python
# ❌ BAD
user = await User.get_or_none(id=1)
print(user.name)  # mypy error!

# ✅ GOOD
user = await User.get_or_none(id=1)
if user:
    print(user.name)
```

### 3. Забыли await

```python
# ❌ BAD
steps = get_steps()  # mypy error: Coroutine not awaited

# ✅ GOOD
steps = await get_steps()
```

---

## 🎯 Когда использовать `Any`

```python
from typing import Any

# Динамические данные из JSON
def process_webhook(data: dict[str, Any]) -> None:
    ...

# Сложные generic типы (временно)
def complex_function() -> Any:
    ...  # TODO: добавить точный тип
```

---

## 🔍 Игнорирование ошибок (крайний случай!)

```python
# Игнорировать конкретную строку
result = dynamic_call()  # type: ignore[misc]

# Игнорировать весь файл (в начале)
# type: ignore

# Игнорировать конкретную функцию
def legacy_code() -> None:  # type: ignore
    ...
```

---

## ✅ Best Practices

1. ✅ Всегда указывай `-> None` для функций без возврата
2. ✅ Используй `| None` вместо `Optional[T]`
3. ✅ Типизируй JSON: `list[int]`, `dict[str, str]`
4. ✅ Проверяй `.get_or_none()` на None
5. ✅ Запускай mypy перед коммитом

---

## 📚 Документация

- Полное руководство: `docs/MYPY_GUIDE.md`
- Конфигурация: `mypy.ini`
- Официальная документация: https://mypy.readthedocs.io/

