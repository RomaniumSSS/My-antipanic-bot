# 001 — MVP Foundation: Базовая функциональность Antipanic Bot

## Objective
Завершить MVP Antipanic Bot: интегрировать готовую инфраструктуру, добавить AI-методы и создать все handlers для полного flow (онбординг → утро → шаги → застрял → вечер → недельный отчёт).

---

## Уже реализовано ✅

| Компонент | Статус |
|-----------|--------|
| `config.py` | ✅ BOT_TOKEN, OPENAI_KEY, ALLOWED_USER_IDS, OPENAI_MODEL |
| `database/models.py` | ✅ User, Goal, Stage, Step, DailyLog |
| `database/config.py` | ✅ TORTOISE_ORM config |
| `main.py` | ✅ Базовая инициализация (Bot, Dispatcher, middleware, DB) |
| `bot/states.py` | ✅ Все FSM states |
| `bot/callbacks/data.py` | ✅ Все CallbackData фабрики |
| `bot/middlewares/access.py` | ✅ Whitelist middleware |
| `bot/keyboards.py` | ✅ Все клавиатуры (energy, confirm, blocker, rating, step_actions, steps_list, yes_no) |
| `services/ai.py` | ✅ Базовый wrapper с retry |
| `services/scheduler.py` | ✅ AsyncScheduler + все API (setup/pause/remove reminders) |
| `handlers/start.py` | ✅ Базовые /start, /help, /id |
| `handlers/health.py` | ✅ /ping |

---

## Proposed Steps (что осталось реализовать)

### Фаза 0: Финализация инфраструктуры

**0.1** Интегрировать scheduler в `main.py`
```python
# Добавить в main.py:
from src.services import scheduler

async def on_startup(bot: Bot):
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    scheduler.set_bot(bot)
    await scheduler.start()

async def on_shutdown():
    await scheduler.stop()
    await Tortoise.close_connections()
```
- [ ] Передать bot в on_startup
- [ ] Вызвать `scheduler.set_bot(bot)` и `scheduler.start()`
- [ ] Вызвать `scheduler.stop()` в on_shutdown

**0.2** Добавить AI промпты и методы в `services/ai.py`
- [ ] Константы: `SYSTEM_PROMPT`, `DECOMPOSE_PROMPT`, `STEPS_PROMPT`, `MICROHIT_PROMPT`
- [ ] Метод `decompose_goal(goal_text, deadline) -> List[dict]` — разбивка цели на 2-4 этапа
- [ ] Метод `generate_steps(stage, energy, mood) -> List[dict]` — генерация 1-3 шагов на день
- [ ] Метод `get_microhit(step, blocker_type) -> str` — микро-удар для застревания

---

### Фаза 1: Onboarding Flow

**1.1** Переписать `handlers/start.py` с логикой пользователя
- [ ] /start → проверка User в БД по telegram_id
  - Новый: создать User → FSM `OnboardingStates.waiting_for_goal`
  - Существующий без активной цели: предложить создать
  - Существующий с активной целью: показать статус + меню
- [ ] Handler для ввода цели → сохранение в FSM data
- [ ] Handler для дедлайна (дата) → сохранение в FSM data

**1.2** Создать `handlers/onboarding.py`
- [ ] После ввода дедлайна: вызов `ai_service.decompose_goal()`
- [ ] Показ этапов с `confirm_keyboard()`
- [ ] При "Да": создание Goal + Stages в БД → переход к menu/ожиданию утра
- [ ] При "Редактировать": переход к ручному вводу этапов (упрощённо — текстом)
- [ ] Вызов `setup_user_reminders()` после создания цели

---

### Фаза 2: Morning Flow

**2.1** Создать `handlers/morning.py`
- [ ] /morning → проверка активной цели (если нет — редирект на онбординг)
- [ ] Показ `energy_keyboard()` → FSM `MorningStates.waiting_for_energy`
- [ ] После выбора энергии → запрос состояния (текстом) → FSM `waiting_for_mood`
- [ ] После состояния → вызов `ai_service.generate_steps()`
- [ ] Создание Step записей + DailyLog в БД
- [ ] Показ шагов с `steps_list_keyboard()` или `step_actions_keyboard()`

---

### Фаза 3: Step Actions + Stuck Flow

**3.1** Создать `handlers/steps.py`
- [ ] Callback `StepCallback(action=done)` → отметка step.status="completed", +XP
- [ ] Callback `StepCallback(action=skip)` → запрос причины пропуска (текст)
- [ ] Callback `StepCallback(action=stuck)` → переход в `StuckStates`

**3.2** Создать `handlers/stuck.py`
- [ ] Показ `blocker_keyboard()` → FSM `StuckStates.waiting_for_blocker`
- [ ] После выбора блокера:
  - Если "unclear" → запрос деталей (текст)
  - Иначе → сразу к микро-удару
- [ ] Вызов `ai_service.get_microhit()`
- [ ] Показ микро-удара пользователю

---

### Фаза 4: Evening Flow

**4.1** Создать `handlers/evening.py`
- [ ] /evening → показ шагов дня с отметкой выполнения
- [ ] Если есть неотмеченные → предложение отметить (done/skip)
- [ ] После всех отметок → `rating_keyboard()` для оценки дня
- [ ] Обновление streak, XP в User
- [ ] Короткий итог дня (текст)

---

### Фаза 5: Weekly Report

**5.1** Добавить /weekly handler
- [ ] Агрегация DailyLog за последние 7 дней
- [ ] Статистика: выполнено шагов, средняя энергия, текущий streak
- [ ] Прогресс по цели/этапу
- [ ] Простой текстовый отчёт

---

### Фаза 6: Интеграция и регистрация

**6.1** Обновить `handlers/__init__.py`
- [ ] Импорт и регистрация всех роутеров:
  - start_router
  - health_router  
  - onboarding_router
  - morning_router
  - steps_router
  - stuck_router
  - evening_router

**6.2** Добавить команду /reminders (опционально для MVP)
- [ ] Показ текущего времени напоминаний
- [ ] Изменение времени утреннего/вечернего напоминания

**6.3** Финальное тестирование flow
- [ ] /start → цель → этапы → подтверждение
- [ ] /morning → энергия → состояние → шаги
- [ ] Кнопки шагов (сделал/пропустить/застрял)
- [ ] Застрял → блокер → микро-удар
- [ ] /evening → отметки → оценка дня
- [ ] /weekly → статистика

---

## Порядок реализации

```
0.1 scheduler интеграция (5 мин)
    ↓
0.2 AI промпты + методы (30 мин)
    ↓
1.x Onboarding handlers (45 мин)
    ↓
2.x Morning handler (30 мин)
    ↓
3.x Steps + Stuck handlers (45 мин)
    ↓
4.x Evening handler (30 мин)
    ↓
5.x Weekly handler (20 мин)
    ↓
6.x Регистрация + тест (15 мин)
```

**Оценка**: ~3-4 часа работы

---

## Risks

| Риск | Митигация |
|------|-----------|
| OpenAI API latency | Fallback сообщения уже есть в ai.py |
| Сложные edge cases в FSM | Graceful fallback на /start при ошибках |
| Scheduler не срабатывает | Логирование, ручные команды /morning /evening |

---

## Rollback

- Каждая фаза — отдельный коммит
- При критических проблемах: `git revert` к предыдущей фазе
- БД: SQLite файл можно удалить и пересоздать схему

---

## Готово к реализации

> ✅ План обновлён. Можно начинать с Фазы 0.1 (интеграция scheduler).
