# Руководство по mypy для Antipanic Bot

## 🎯 Что такое mypy?

**mypy** — статический анализатор типов для Python. Проверяет код **до запуска**, находя ошибки типов и несоответствия.

### Зачем нужен?

1. **Раннее обнаружение ошибок** — баги находятся до деплоя
2. **Самодокументирование** — типы показывают, что функция принимает и возвращает
3. **Лучшее автодополнение** — IDE знает типы и подсказывает методы
4. **Безопасный рефакторинг** — mypy покажет все места, требующие изменений
5. **Предотвращение None errors** — особенно важно для `.get_or_none()`

---

## 🚀 Быстрый старт

### Установка

```bash
pip install -r requirements.txt  # mypy уже в зависимостях
```

### Запуск проверки

```bash
# Проверить весь проект
mypy src/

# Проверить конкретный модуль
mypy src/core/domain/

# Проверить один файл
mypy src/services/session.py
```

### Интеграция в CI/CD

```yaml
# .github/workflows/ci.yml
- name: Type check with mypy
  run: mypy src/
```

---

## 📝 Конфигурация

Настройки в `mypy.ini`:

```ini
[mypy]
python_version = 3.11
warn_return_any = True
check_untyped_defs = True
no_implicit_optional = True
strict_optional = True
ignore_missing_imports = True
```

### Строгие модули

Для критичных модулей включена строгая проверка:

- `src/core/domain/*` — чистые функции, 100% типизация
- `src/core/use_cases/*` — бизнес-логика
- `src/storage/*` — репозитории

---

## 🔧 Практические примеры

### 1. Типизация функций

```python
# ❌ БЕЗ типов
async def get_user(telegram_id):
    return await User.get_or_none(telegram_id=telegram_id)

# ✅ С типами
async def get_user(telegram_id: int) -> User | None:
    return await User.get_or_none(telegram_id=telegram_id)
```

### 2. Tortoise ORM relations

```python
from tortoise import fields

class Goal(models.Model):
    # ✅ Правильно — с типом
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="goals", on_delete=fields.CASCADE
    )
    
    # ✅ Reverse relation
    stages: fields.ReverseRelation["Stage"]
```

### 3. JSON поля

```python
class DailyLog(models.Model):
    # ✅ Указываем структуру JSON
    assigned_step_ids: list[int] = fields.JSONField(default=[])
    skip_reasons: dict[str, str] = fields.JSONField(default={})
```

### 4. Optional и None checks

```python
# mypy заставит проверить на None
user = await get_user(telegram_id)  # type: User | None

# ❌ mypy error: Item "None" has no attribute "xp"
print(user.xp)

# ✅ Правильно
if user:
    print(user.xp)
```

### 5. Забытый await

```python
# ❌ mypy error: Value of type "Coroutine[...]" must be awaited
steps = get_steps()

# ✅ Правильно
steps = await get_steps()
```

---

## 🐛 Частые ошибки и решения

### Ошибка: "Need type annotation"

```python
# ❌ Проблема
user = fields.ForeignKeyField(...)

# ✅ Решение
user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(...)
```

### Ошибка: "Incompatible types in assignment"

```python
# ❌ Проблема
def get_xp(step: Step) -> int:
    return step.xp_reward

user.xp = get_xp(None)  # mypy error!

# ✅ Решение — проверка на None
if step:
    user.xp = get_xp(step)
```

### Ошибка: "Missing return statement"

```python
# ❌ Проблема
def process_data(data: dict) -> str:
    if data:
        return data["name"]
    # mypy: Missing return statement

# ✅ Решение
def process_data(data: dict) -> str:
    if data:
        return data["name"]
    return "Unknown"  # Явный return
```

---

## 📊 Текущий статус проекта

```
✅ mypy установлен и настроен
✅ Базовая типизация: 81% функций
✅ Строгие модули: core/domain, core/use_cases, storage
✅ Tortoise ORM relations типизированы
✅ JSON поля аннотированы
```

---

## 🎓 Постепенное внедрение

### Этап 1: Базовая проверка (СДЕЛАНО ✅)
- Установка mypy
- Конфигурация mypy.ini
- Типизация models.py
- Проверка domain модулей

### Этап 2: Расширение (TODO)
- Добавить return types во все handlers
- Типизировать все repositories
- Включить `disallow_untyped_defs` для services/

### Этап 3: Строгий режим (TODO)
- `disallow_any_generics = True`
- `disallow_incomplete_defs = True`
- Полная типизация всего проекта

---

## 🔗 Полезные ссылки

- [mypy документация](https://mypy.readthedocs.io/)
- [Tortoise ORM type hints](https://tortoise.github.io/type_hints.html)
- [Python typing cheat sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)

---

## 💡 Best Practices

1. **Всегда указывай return type** — даже если это `None`
2. **Используй `| None` вместо `Optional`** — современный синтаксис Python 3.10+
3. **Проверяй на None** перед использованием `.get_or_none()`
4. **Типизируй JSON поля** — `list[int]`, `dict[str, str]`
5. **Запускай mypy перед коммитом** — ловит ошибки рано

---

## 🚨 Когда игнорировать mypy

Используй `# type: ignore` только в крайних случаях:

```python
# Сложный dynamic код, который mypy не понимает
result = complex_dynamic_function()  # type: ignore[misc]
```

**Но лучше исправить код, чем игнорировать!**

