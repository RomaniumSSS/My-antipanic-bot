# aiogram 3.x (Quick Reference)

## 1. CallbackData Factory (ОБЯЗАТЕЛЬНО!)

**НЕ ИСПОЛЬЗУЙ** raw-строки для `callback_data`!

```python
from aiogram.filters.callback_data import CallbackData
from enum import Enum

class EnergyAction(str, Enum):
    set = "set"
    skip = "skip"

class EnergyCallback(CallbackData, prefix="energy"):
    action: EnergyAction
    value: int | None = None

# Использование в клавиатурах
def energy_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(
            text=str(i),
            callback_data=EnergyCallback(action=EnergyAction.set, value=i)
        )
    builder.adjust(5, 5)
    return builder.as_markup()

# Фильтрация в хендлерах
from aiogram import F

@router.callback_query(EnergyCallback.filter(F.action == EnergyAction.set))
async def on_energy_set(callback: CallbackQuery, callback_data: EnergyCallback):
    energy = callback_data.value
    await callback.answer(f"Энергия: {energy}")
```

## 2. Magic Filter F

```python
from aiogram import F

# Базовые
F.text                              # есть текст
F.text == "/start"                  # точное совпадение
F.from_user.id == 12345             # проверка user_id
F.text.startswith("/")              # начинается с
F.text.contains("привет")           # содержит
F.from_user.id.in_({111, 222})      # в списке
~F.text                             # НЕТ текста (инверсия)

# Комбинирование
(F.from_user.id == 42) & (F.text == "admin")              # AND
F.text.startswith("!") | F.text.startswith("/")           # OR
```

## 3. Роутеры

```python
# src/bot/handlers/morning.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

router = Router(name="morning")

@router.message(F.text == "/morning")
async def cmd_morning(message: Message, state: FSMContext):
    await state.set_state(MorningStates.waiting_for_energy)
    await message.answer("Как энергия?", reply_markup=energy_keyboard())

@router.callback_query(
    MorningStates.waiting_for_energy,
    EnergyCallback.filter(F.action == EnergyAction.set)
)
async def on_energy(callback: CallbackQuery, callback_data: EnergyCallback, state: FSMContext):
    await state.update_data(energy=callback_data.value)
    await callback.answer()

# Регистрация в main.py
from src.bot.handlers import morning

dp.include_router(morning.router)
```

## 4. FSM States

```python
from aiogram.fsm.state import State, StatesGroup

class OnboardingStates(StatesGroup):
    waiting_for_goal = State()
    waiting_for_deadline = State()
    confirming_stages = State()

# Работа с состоянием
await state.set_state(OnboardingStates.waiting_for_goal)
await state.update_data(goal_text=message.text)
data = await state.get_data()
goal = data.get("goal_text")
await state.clear()

# Фильтрация по состоянию
@router.message(OnboardingStates.waiting_for_goal)
async def process_goal(message: Message, state: FSMContext):
    ...
```

## 5. Middleware

### CallbackAnswerMiddleware (ОБЯЗАТЕЛЬНО!)

```python
from aiogram.utils.callback_answer import CallbackAnswerMiddleware

dp = Dispatcher()
dp.callback_query.middleware(CallbackAnswerMiddleware())
```

### Whitelist Middleware

```python
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

class AccessMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if not config.ALLOWED_USER_IDS:
            return await handler(event, data)
        
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
        
        if user_id and user_id in config.ALLOWED_USER_IDS:
            return await handler(event, data)
        
        return None  # Игнорируем неразрешённых

# Регистрация
dp.message.middleware(AccessMiddleware())
dp.callback_query.middleware(AccessMiddleware())
```

## 6. Error Handler

```python
from aiogram.types import ErrorEvent

@dp.error()
async def global_error_handler(event: ErrorEvent):
    logger.exception("Unhandled exception", exc_info=event.exception)
    
    update = event.update
    if update.message:
        await update.message.answer("Ошибка. Попробуй позже.")
    elif update.callback_query:
        await update.callback_query.answer("Ошибка!", show_alert=True)
```

## 7. Клавиатуры

```python
from aiogram.utils.keyboard import InlineKeyboardBuilder

def blocker_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="😨 Страшно", 
                   callback_data=BlockerCallback(type=BlockerType.fear))
    builder.button(text="🤷 Не знаю", 
                   callback_data=BlockerCallback(type=BlockerType.unclear))
    builder.adjust(2)  # 2 кнопки в ряд
    return builder.as_markup()

# ReplyKeyboard
from aiogram.utils.keyboard import ReplyKeyboardBuilder

def yes_no_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="Да")
    builder.button(text="Нет")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)
```

## Антипаттерны

```python
# ❌ Raw callback_data
builder.button(text="1", callback_data="energy:1")

# ✅ Правильно
builder.button(text="1", callback_data=EnergyCallback(action=EnergyAction.set, value=1))

# ❌ Парсинг callback_data вручную
@router.callback_query(F.data.startswith("energy:"))
async def on_energy(callback: CallbackQuery):
    value = int(callback.data.split(":")[1])

# ✅ Правильно
@router.callback_query(EnergyCallback.filter(F.action == EnergyAction.set))
async def on_energy(callback: CallbackQuery, callback_data: EnergyCallback):
    value = callback_data.value

# ❌ Забыть callback.answer()
@router.callback_query(...)
async def handler(callback: CallbackQuery):
    await callback.message.answer("Done")
    # Telegram покажет "loading"!

# ✅ Правильно — используй CallbackAnswerMiddleware или явный answer
await callback.answer()

# ❌ Бизнес-логика в хендлерах
@router.message(...)
async def handler(message: Message):
    # 50 строк БД и AI логики...

# ✅ Правильно — вынеси в use-case
result = await assign_morning_steps_use_case.create_steps(user, goal)
await message.answer(format_result(result))
```

## Структура проекта

```
src/bot/
├── handlers/
│   ├── __init__.py          # Экспорт роутеров
│   ├── start.py
│   ├── morning.py
│   ├── stuck.py
│   └── evening.py
├── callbacks/
│   └── data.py              # CallbackData фабрики
├── keyboards.py             # Все клавиатуры
├── states.py                # FSM StatesGroup
└── middlewares/
    └── access.py
```

## Чеклист

- [ ] `CallbackData` фабрики (НЕ raw строки!)
- [ ] `CallbackAnswerMiddleware` подключен
- [ ] FSM состояния в `StatesGroup`
- [ ] Роутеры зарегистрированы в `Dispatcher`
- [ ] Middleware подключены
- [ ] Типы: `Message`, `CallbackQuery`, `FSMContext`
- [ ] НЕТ бизнес-логики в хендлерах
