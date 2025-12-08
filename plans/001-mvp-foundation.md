# 001 — MVP Foundation: Базовая функциональность Antipanic Bot

## Objective
Создать рабочий MVP Antipanic Bot с полной инфраструктурой (БД, scheduler, AI), готовый к расширению. MVP включает: онбординг с постановкой цели, утренний ритуал с генерацией шагов, кнопку «Застрял» с микро-ударом, отметку выполнения и простой недельный отчёт.

---

## Текущее состояние (что уже есть)

| Компонент | Статус | Комментарий |
|-----------|--------|-------------|
| Структура проекта | ✅ | По tech.md |
| config.py | ✅ | BOT_TOKEN, OPENAI_KEY, ALLOWED_USER_IDS |
| database/models.py | ✅ | User, Goal, Stage, Step, DailyLog |
| database/config.py | ✅ | TORTOISE_ORM config |
| main.py | ✅ | Инициализация бота, DB, middleware |
| bot/states.py | ✅ | Все FSM states |
| bot/callbacks/data.py | ✅ | Все CallbackData фабрики |
| bot/middlewares/access.py | ✅ | Whitelist middleware |
| services/ai.py | ✅ | Базовый wrapper с retry |
| handlers/start.py | ⚠️ | Только /start, /help, /id — нет онбординга |
| handlers/health.py | ✅ | /ping |
| bot/keyboards.py | ❌ | Пустой или базовый |
| services/scheduler.py | ❌ | Не создан |
| AI Prompts | ❌ | Не добавлены в ai.py |

---

## Proposed Steps

### Фаза 0: Инфраструктура (подготовка)

**0.1** Создать `services/scheduler.py`
- AsyncScheduler с функциями start/stop
- Задачи: `send_morning_reminder`, `send_evening_reminder`
- API: `setup_user_reminders`, `pause_user_reminders`, `remove_user_reminders`
- Интеграция с main.py (on_startup/on_shutdown)

**0.2** Дополнить `services/ai.py` промптами и методами
- Константы: `SYSTEM_PROMPT`, `DECOMPOSE_PROMPT`, `STEPS_PROMPT`, `MICROHIT_PROMPT`
- Методы: `decompose_goal()`, `generate_steps()`, `get_microhit()`

**0.3** Создать `bot/keyboards.py`
- `energy_keyboard()` — кнопки 1-10
- `confirm_keyboard()` — Да / Редактировать / Отмена
- `blocker_keyboard()` — 4 типа блокеров
- `step_actions_keyboard(step_id)` — Сделал / Пропустить / Застрял
- `rating_keyboard()` — оценка дня 1-5

---

### Фаза 1: Onboarding Flow

**1.1** Переписать `handlers/start.py`
- /start → проверка есть ли User в БД
  - Новый: создать User → перейти в OnboardingStates.waiting_for_goal
  - Существующий без активной цели: предложить создать
  - Существующий с целью: показать статус + меню
- Обработка ввода цели → сохранение в FSM data
- Обработка дедлайна (дата) → сохранение

**1.2** Создать `handlers/onboarding.py` (или дополнить start.py)
- После ввода дедлайна: вызов `ai_service.decompose_goal()`
- Показ этапов с клавиатурой подтверждения
- При "Да": создание Goal + Stages в БД → переход к "первый шаг"
- При "Редактировать": переход к вводу этапов вручную (упрощённо)

---

### Фаза 2: Morning Flow

**2.1** Создать `handlers/morning.py`
- /morning → проверка активной цели
- Показ клавиатуры энергии (1-10)
- После выбора энергии → запрос состояния (текст)
- После состояния → вызов `ai_service.generate_steps()`
- Создание Step записей + DailyLog
- Показ шагов с клавиатурой действий

---

### Фаза 3: Step Actions + Stuck Flow

**3.1** Создать `handlers/steps.py`
- Callback на StepCallback.done → отметка completed, +XP
- Callback на StepCallback.skip → запрос причины
- Callback на StepCallback.stuck → переход в StuckStates

**3.2** Создать `handlers/stuck.py`
- Показ клавиатуры блокеров
- После выбора блокера: если "unclear" → запрос деталей
- Вызов `ai_service.get_microhit()`
- Показ микро-удара

---

### Фаза 4: Evening Flow

**4.1** Создать `handlers/evening.py`
- /evening → показ шагов дня с отметкой что сделано
- Если не все отмечены → предложение отметить
- После отметки → оценка дня (1-5)
- Обновление streak, XP
- Короткий итог дня

---

### Фаза 5: Weekly Report

**5.1** Добавить /weekly в handlers
- Агрегация DailyLog за последние 7 дней
- Статистика: выполнено шагов, средняя энергия, текущий streak
- Прогресс по цели/этапу
- Простой текстовый отчёт

---

### Фаза 6: Интеграция и полировка

**6.1** Подключить scheduler к flow
- При создании User → `setup_user_reminders()`
- Команда /reminders для настройки времени

**6.2** Регистрация всех роутеров в `handlers/__init__.py`
- start, onboarding, morning, steps, stuck, evening

**6.3** Тестирование полного flow
- /start → цель → утро → шаги → застрял → вечер → /weekly

---

## Deliverables (что получим в конце)

1. **Работающий MVP** со всеми функциями из product.md
2. **Инфраструктура**:
   - SQLite БД с миграциями (Aerich)
   - APScheduler для напоминаний
   - OpenAI интеграция с промптами
3. **Handlers для всех flow**:
   - Onboarding: /start → цель → этапы
   - Morning: /morning → энергия → шаги
   - Stuck: кнопка → блокер → микро-удар
   - Evening: /evening → отметки → оценка
   - Weekly: /weekly → статистика
4. **Готовность к расширению**: чёткая структура, документация, AICODE-комментарии

---

## Risks

| Риск | Митигация |
|------|-----------|
| OpenAI API latency | Fallback сообщения, retry с tenacity |
| Сложные edge cases в FSM | Graceful fallback на /start при ошибках |
| Миграции схемы | Использовать Aerich с самого начала |
| Перегрузка пользователя | Лимиты из product.md (1-3 шага, 1-2 цели) |

---

## Rollback

- Каждая фаза — отдельный коммит/PR
- При критических проблемах: откат к предыдущей фазе через git
- БД: backup перед каждой миграцией

---

## Порядок реализации (рекомендуемый)

```
Фаза 0 (инфра) → Фаза 1 (onboarding) → Фаза 2 (morning) 
    → Фаза 3 (steps/stuck) → Фаза 4 (evening) → Фаза 5 (weekly) → Фаза 6 (polish)
```

**Оценка времени**: ~4-6 сессий разработки (зависит от глубины тестирования).

---

## Согласование

> ⏳ **Ожидает подтверждения от пользователя перед началом реализации.**

