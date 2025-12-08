# Правила разработки на aiogram 3.x

Этот документ содержит обязательные правила и паттерны для работы с aiogram 3.x в проекте Antipanic Bot.

---

## 1. CallbackData Factory (ОБЯЗАТЕЛЬНО)

**НЕ ИСПОЛЬЗУЙ** raw-строки для `callback_data`. Всегда создавай типизированные фабрики.

### Создание фабрики

```python
from aiogram.filters.callback_data import CallbackData
from enum import Enum

class EnergyAction(str, Enum):
    set = "set"
    skip = "skip"

class EnergyCallback(CallbackData, prefix="energy"):
    action: EnergyAction
    value: int | None = None
```

### Использование в клавиатурах

```python
from aiogram.utils.keyboard import InlineKeyboardBuilder

def energy_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(
            text=str(i),
            callback_data=EnergyCallback(action=EnergyAction.set, value=i)
        )
    builder.adjust(5, 5)
    return builder.as_markup()
```

### Фильтрация в хендлерах

```python
from aiogram import F

@router.callback_query(EnergyCallback.filter(F.action == EnergyAction.set))
async def on_energy_set(callback: CallbackQuery, callback_data: EnergyCallback):
    energy = callback_data.value
    await callback.answer(f"Энергия: {energy}")
```

---

## 2. Magic Filter F (паттерны)

### Базовые проверки

```python
from aiogram import F

# Проверка существования
F.photo                              # есть фото
F.text                               # есть текст

# Сравнение
F.text == "/start"                   # точное совпадение
F.from_user.id == 12345              # проверка user_id
F.text.lower() == "да"               # lowercase сравнение

# Методы строк
F.text.startswith("/")               # начинается с
F.text.endswith("!")                 # заканчивается на
F.text.contains("привет")            # содержит

# Коллекции
F.from_user.id.in_({111, 222, 333})  # в списке

# Инверсия
~F.text                              # НЕТ текста
~F.text.startswith("spam")           # НЕ начинается с
```

### Комбинирование фильтров

```python
# AND — оператор &
(F.from_user.id == 42) & (F.text == "admin")

# OR — оператор |
F.text.startswith("!") | F.text.startswith("/")

# Сложные условия
(F.from_user.id.in_({42, 777})) & (F.text.startswith("/") | F.text.startswith("!"))
```

### Извлечение данных через .as_()

```python
from re import Match

@router.message(F.text.regexp(r"^(\d+)$").as_("digits"))
async def handle_digits(message: Message, digits: Match[str]):
    number = int(digits.group(1))
    await message.answer(f"Число: {number}")
```

---

## 3. Роутеры и структура хендлеров

### Структура файлов

```
src/bot/
├── handlers/
│   ├── __init__.py          # Экспорт всех роутеров
│   ├── start.py             # /start, онбординг
│   ├── morning.py           # Утренний флоу
│   ├── stuck.py             # Застрял
│   └── evening.py           # Вечерний отчёт
├── callbacks/
│   └── data.py              # Все CallbackData фабрики
├── keyboards.py             # Все клавиатуры
├── states.py                # FSM StatesGroup
└── middlewares/
    └── access.py            # Middleware проверки доступа
```

### Регистрация роутеров

```python
# src/bot/handlers/__init__.py
from . import start, morning, stuck, evening

__all__ = ["start", "morning", "stuck", "evening"]
```

```python
# src/main.py
from src.bot.handlers import start, morning, stuck, evening

dp = Dispatcher()
dp.include_routers(
    start.router,
    morning.router,
    stuck.router,
    evening.router,
)
```

### Шаблон роутера

```python
# src/bot/handlers/morning.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.bot.states import MorningStates
from src.bot.callbacks.data import EnergyCallback, EnergyAction
from src.bot.keyboards import energy_keyboard

router = Router(name="morning")


@router.message(F.text == "/morning")
async def cmd_morning(message: Message, state: FSMContext):
    await state.set_state(MorningStates.waiting_for_energy)
    await message.answer("Как твоя энергия? (1-10)", reply_markup=energy_keyboard())


@router.callback_query(
    MorningStates.waiting_for_energy,
    EnergyCallback.filter(F.action == EnergyAction.set)
)
async def on_energy(callback: CallbackQuery, callback_data: EnergyCallback, state: FSMContext):
    await state.update_data(energy=callback_data.value)
    await state.set_state(MorningStates.waiting_for_mood)
    await callback.message.answer("Как себя чувствуешь? (1-2 слова)")
    await callback.answer()
```

---

## 4. FSM (Finite State Machine)

### Определение состояний

```python
from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    waiting_for_goal = State()
    waiting_for_deadline = State()
    confirming_stages = State()
```

### Работа с состоянием

```python
# Установка состояния
await state.set_state(OnboardingStates.waiting_for_goal)

# Сохранение данных
await state.update_data(goal_text=message.text)

# Получение данных
data = await state.get_data()
goal = data.get("goal_text")

# Очистка состояния
await state.clear()
```

### Фильтрация по состоянию

```python
@router.message(OnboardingStates.waiting_for_goal)
async def process_goal(message: Message, state: FSMContext):
    ...

# Любое состояние из группы
@router.message(OnboardingStates)
async def any_onboarding_state(message: Message, state: FSMContext):
    ...
```

---

## 5. Middleware

### CallbackAnswerMiddleware (ОБЯЗАТЕЛЬНО)

Автоматически отвечает на все callback query после выполнения хендлера.

```python
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

dp = Dispatcher()
dp.callback_query.middleware(CallbackAnswerMiddleware())
```

### Кастомная middleware для whitelist

```python
# src/bot/middlewares/access.py
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from src.config import config


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Если whitelist пустой — пропускаем всех
        if not config.ALLOWED_USER_IDS:
            return await handler(event, data)

        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id and user_id in config.ALLOWED_USER_IDS:
            return await handler(event, data)

        # Молча игнорируем неразрешённых
        return None
```

### Регистрация middleware

```python
from src.bot.middlewares.access import AccessMiddleware

dp = Dispatcher()
dp.message.middleware(AccessMiddleware())
dp.callback_query.middleware(AccessMiddleware())
```

---

## 6. Обработка ошибок

### Глобальный error handler

```python
from aiogram.types import ErrorEvent
import logging

logger = logging.getLogger(__name__)

@dp.error()
async def global_error_handler(event: ErrorEvent):
    logger.exception(
        "Unhandled exception: %s",
        event.exception,
        exc_info=event.exception
    )
    # Можно уведомить пользователя
    update = event.update
    if update.message:
        await update.message.answer("Произошла ошибка. Попробуй позже.")
    elif update.callback_query:
        await update.callback_query.answer("Ошибка!", show_alert=True)
```

### Error handler на роутере

```python
from aiogram.filters import ExceptionTypeFilter

class MyCustomError(Exception):
    pass

@router.error(ExceptionTypeFilter(MyCustomError), F.update.message.as_("message"))
async def handle_custom_error(event: ErrorEvent, message: Message):
    await message.answer("Специфическая ошибка обработана.")
```

---

## 7. Dependency Injection

### Инъекция через Dispatcher

```python
dp = Dispatcher(
    db=database_connection,
    ai_service=ai_service,
)

# Или динамически
dp["scheduler"] = scheduler
```

### Использование в хендлерах

```python
@router.message(Command("stats"))
async def cmd_stats(message: Message, db: DatabaseConnection):
    # db автоматически передан из контекста
    stats = await db.get_user_stats(message.from_user.id)
    await message.answer(str(stats))
```

---

## 8. Клавиатуры

### InlineKeyboardBuilder

```python
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def blocker_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="😨 Страшно", callback_data=BlockerCallback(type=BlockerType.fear))
    builder.button(text="🤷 Не знаю с чего", callback_data=BlockerCallback(type=BlockerType.unclear))
    builder.button(text="⏰ Нет времени", callback_data=BlockerCallback(type=BlockerType.no_time))
    builder.button(text="😴 Нет сил", callback_data=BlockerCallback(type=BlockerType.no_energy))
    builder.adjust(2, 2)
    return builder.as_markup()
```

### ReplyKeyboardBuilder

```python
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup

def yes_no_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="Да")
    builder.button(text="Нет")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)
```

---

## 9. Антипаттерны (НЕ ДЕЛАЙ ТАК)

### ❌ Raw callback_data строки

```python
# ПЛОХО
builder.button(text="1", callback_data="energy:1")

# ХОРОШО
builder.button(text="1", callback_data=EnergyCallback(action=EnergyAction.set, value=1))
```

### ❌ Парсинг callback_data вручную

```python
# ПЛОХО
@router.callback_query(F.data.startswith("energy:"))
async def on_energy(callback: CallbackQuery):
    value = int(callback.data.split(":")[1])

# ХОРОШО
@router.callback_query(EnergyCallback.filter(F.action == EnergyAction.set))
async def on_energy(callback: CallbackQuery, callback_data: EnergyCallback):
    value = callback_data.value
```

### ❌ Забыть callback.answer()

```python
# ПЛОХО — Telegram покажет "loading"
@router.callback_query(...)
async def handler(callback: CallbackQuery):
    await callback.message.answer("Done")
    # забыли callback.answer()

# ХОРОШО — используй CallbackAnswerMiddleware или явный answer
@router.callback_query(...)
async def handler(callback: CallbackQuery):
    await callback.message.answer("Done")
    await callback.answer()
```

### ❌ Бизнес-логика в хендлерах

```python
# ПЛОХО
@router.message(...)
async def handler(message: Message):
    # 50 строк логики работы с БД и AI
    ...

# ХОРОШО — выноси в сервисы
@router.message(...)
async def handler(message: Message, state: FSMContext):
    data = await state.get_data()
    result = await step_service.generate_steps(data["goal"], data["energy"])
    await message.answer(format_steps(result))
```

---

## 10. Чеклист перед коммитом

- [ ] Все `callback_data` используют `CallbackData` фабрики
- [ ] Все callback хендлеры явно вызывают `callback.answer()` или используют `CallbackAnswerMiddleware`
- [ ] FSM состояния определены в `StatesGroup`
- [ ] Роутеры зарегистрированы в `Dispatcher`
- [ ] Middleware подключены (access, callback_answer)
- [ ] Типы указаны: `Message`, `CallbackQuery`, `FSMContext`
- [ ] Нет бизнес-логики в хендлерах — только вызовы сервисов

