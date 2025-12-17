# Type Safety Improvements (Must-Have Only)

## Цель
Исправить только критические проблемы, которые реально мешают разработке и приводят к багам.

## Must-Have Improvements

### 1. Type-Safe Markdown Formatter ⭐ КРИТИЧНО

**Проблема**:
Мы ТОЛЬКО ЧТО исправили 33 места где забыли `escape_markdown()`. При каждом новом feature это будет повторяться.

**Решение**:
Простой helper class, который автоматически экранирует:

```python
# src/bot/formatters.py
from src.bot.utils import escape_markdown

class MarkdownFormatter:
    @staticmethod
    def bold(*parts: str | int | float) -> str:
        escaped = " ".join(escape_markdown(str(p)) for p in parts)
        return f"*{escaped}*"

    @staticmethod
    def italic(*parts: str | int | float) -> str:
        escaped = " ".join(escape_markdown(str(p)) for p in parts)
        return f"_{escaped}_"

md = MarkdownFormatter()
```

**Использование**:
```python
# Вместо:
f"Goal: *{escape_markdown(goal.title)}*"  # Легко забыть escape_markdown

# Пишем:
f"Goal: {md.bold(goal.title)}"  # Невозможно забыть - всегда safe
```

**Преимущества**:
- ✅ Невозможно забыть экранирование
- ✅ Короче и читабельнее код
- ✅ Никакого overhead или сложности
- ✅ Не меняет архитектуру

**Усилия**: ~30 минут на создание + постепенный рефакторинг handlers

---

### 2. Fix Generic Type Parameters ⭐ КРИТИЧНО

**Проблема**:
Mypy strict mode падает на `list` и `dict` без параметров типа в keyboards.py

**Решение**:
Добавить параметры типов:

```python
# До:
def goal_select_keyboard(goals: list) -> InlineKeyboardMarkup:

# После:
def goal_select_keyboard(goals: list[Goal]) -> InlineKeyboardMarkup:
```

**Места для исправления**:
- `keyboards.py`: 3 функции с generic `list`
- `handlers/morning.py`: 1 функция без return type
- `handlers/stuck.py`: 1 функция без типов параметров

**Преимущества**:
- ✅ IDE autocomplete работает корректно
- ✅ Ошибки типов обнаруживаются сразу
- ✅ Код самодокументируется

**Усилия**: ~20 минут

---

## Что НЕ делаем (nice-to-have, но не критично)

- ❌ TypedDict для FSM state - работает и так, можно позже
- ❌ Pydantic models - избыточно
- ❌ Validation helpers - можно обойтись существующими проверками
- ❌ Strict mypy в CI/CD - можно включить после первых двух пунктов

## План действий

1. Создать `src/bot/formatters.py` с `MarkdownFormatter`
2. Добавить тесты для formatter
3. Исправить type annotations в `keyboards.py`
4. Постепенно рефакторить handlers на использование `md.*` (по мере работы с ними)

**Итого**: ~1 час работы для решения самых критичных проблем.
