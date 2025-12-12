# План срезания дерева до ядра

**Дата**: 2025-12-12
**Проблема**: Страх и ступор от внутренней неуверенности → бездействие
**Решение (ядро)**: Страх/ступор → микродействие (2-5 мин) → XP/streak → вечерний итог

---

## Философия среза

**Правило**: Если фича не работает НАПРЯМУЮ на путь "ступор → действие → итог" — она идёт в BACKLOG.

Цель — получить стабильное ядро, которое можно:
1. Протестировать на себе 3-7 дней
2. Задеплоить без страха поломки
3. Расширять только после подтверждения работоспособности ядра

---

## Анализ текущего состояния

### Что есть сейчас (структура файлов)

```
src/bot/handlers/
├── start.py         (6.4KB)  - точка входа, квиз → онбординг
├── quiz.py          (10KB)   - 8 вопросов, AI анализ, зависимость
├── onboarding.py    (8KB)    - создание Goal + AI генерация Stages
├── morning.py       (10KB)   - AntipanicSession (новый) + legacy
├── stuck.py         (16KB)   - микроудары (ЯДРО!)
├── evening.py       (7KB)    - вечерний отчёт
├── steps.py         (19KB)   - управление шагами, отметки
├── health.py        (359B)   - /health эндпоинт
├── weekly.py        (5KB)    - недельная рефлексия
└── __init__.py

src/bot/states.py:
- QuizStates (2 состояния)
- OnboardingStates (3 состояния)
- AntipanicSession (6 состояний) ← НОВЫЙ
- StuckStates (4 состояния) ← ЯДРО
- EveningStates (3 состояния)
- OnboardingSprintStates (1 состояние - paywall)
- GoalStates (3 состояния)

src/database/models.py:
- User (xp, level, streak_days, reminder_*)
- Goal (title, deadline, status)
- Stage (order, progress, status) ← ПРОМЕЖУТОЧНЫЙ СЛОЙ
- Step (title, difficulty, xp_reward, status)
- DailyLog (energy, mood, assigned/completed steps, xp_earned)
- QuizResult (answers, dependency_score, diagnosis)
```

---

## Ядро в 1 абзаце (60 секунд для пользователя)

```
Пользователь заходит → говорит что его тормозит (страх/неясность/нет сил)
→ бот даёт микродействие на 2-5 минут через AI
→ пользователь делает → отмечает
→ получает XP + поддерживает streak
→ вечером видит что сделал за день
```

**Это и есть ядро. Всё остальное — надстройки.**

---

## Этап 1: Срезать дерево (2-3 дня)

### 1.1 Удалить полностью (создать BACKLOG.md)

Создать файл `/docs/BACKLOG.md` и переместить туда описание:

#### Удалить файлы:
```bash
src/bot/handlers/health.py          # просто health check
src/bot/handlers/weekly.py          # отложить до стабилизации
src/bot/handlers/quiz.py            # заменить на прямой старт
```

#### Удалить из states.py:
- `QuizStates`
- `OnboardingSprintStates` (paywall - отложить)
- `GoalStates` (дублирует OnboardingStates)

#### Удалить из models.py:
- `QuizResult` (модель + миграция)

#### Удалить из services/:
Проверить, нет ли отдельных сервисов для quiz/weekly.

### 1.2 Упростить резко

#### onboarding.py (8KB → 3KB)
**Было**: Квиз → AI генерирует этапы → подтверждение
**Будет**: Прямой ввод цели → 1 дефолтный этап "Начало" → старт

Логика:
```python
/start (новый пользователь) →
  "Какую цель хочешь достичь?" →
  Ввод цели →
  Создать Goal + 1 активный Stage ("Начало") →
  "Теперь жми Застрял — начнём с микрошага"
```

Убрать:
- AI генерацию этапов (дорого, медленно, не критично)
- Подтверждение этапов
- deadline (опционально, можно добавить позже)

#### start.py (6.4KB → 3KB)
**Было**: Квиз → онбординг, сложная логика
**Будет**: Прямой старт

Логика:
```python
/start:
  if есть active_goal:
    показать статус + меню
  else:
    → onboarding (упрощённый)
```

Убрать:
- Проверку QuizResult
- Проверку onboarding_goal (упростить)
- Сложную логику восстановления

#### morning.py (10KB → 5KB)
**Было**: AntipanicSession (6 состояний) + legacy MorningStates
**Будет**: Только упрощённый AntipanicSession (3-4 состояния)

Логика:
```python
/morning:
  1. Замер напряжения (0-10)
  2. Генерация микродействия через AI
  3. Выполнение + отметка
  4. Короткий фидбек
```

Убрать:
- doing_body_action (отложить)
- offered_deepen (отложить)
- selecting_topic (если одна цель - не нужно)
- Legacy MorningStates полностью

#### evening.py (7KB → 3KB)
**Было**: Отметка что сделано + причина пропуска + оценка дня
**Будет**: Короткий итог дня

Логика:
```python
/evening (или авто-напоминание):
  Показать список assigned_steps
  Кнопки: ✅ Сделано / ⏭️ Пропущено
  Сохранить в DailyLog.completed_step_ids
  Показать: "За сегодня +X XP, streak N дней"
```

Убрать:
- Причины пропуска (детализация)
- Оценка дня (отложить)

#### steps.py (19KB → ???)
Прочитать и понять что там. Возможно, большая часть — legacy или избыточность.

### 1.3 Упростить модели (опционально, но эффективно)

#### Вариант A (радикальный): Goal → Step (без Stage)
```python
# Было:
Goal → Stage → Step

# Будет:
Goal → Step
# Stage можно эмулировать через Step.category или вообще убрать
```

**Плюсы:**
- Проще код
- Меньше сложности в ensure_active_stage
- Быстрее разработка

**Минусы:**
- Нужна миграция БД
- Может понадобиться Stage позже

**Решение:** Отложить до этапа 2, пока просто не трогать Stage, но упростить логику.

#### Вариант B (консервативный): Оставить Stage, но упростить логику

Оставить модели как есть, но:
- Всегда создавать 1 дефолтный активный Stage ("Начало")
- Не генерировать через AI
- Не использовать progress (или считать как count(completed_steps) / count(steps))

---

## Этап 2: Стабилизация ядра (1-2 дня)

### 2.1 Тестирование вручную (критично!)

1. **Тест 1: Новый пользователь**
   - /start → ввод цели → создалась цель
   - /stuck → микродействие → отметить "Сделано"
   - Проверить: XP начислился, DailyLog создался

2. **Тест 2: Повторный день**
   - /morning → микродействие
   - /evening → отметка
   - Проверить: streak увеличился

3. **Тест 3: Застревание**
   - /stuck → выбор блокера → микроудар → фидбек "Ещё"
   - Проверить: новый микроудар генерируется

4. **Тест 4: Смена цели**
   - Попробовать изменить цель (это был баг!)
   - Должна быть команда или кнопка "Изменить цель"

### 2.2 Исправить критичные баги

**Баг из фидбека Geo: "изменить цель"**

Добавить:
```python
/change_goal или кнопка "Изменить цель" в меню:
  - Пометить текущую цель как "paused" или "abandoned"
  - Запустить упрощённый onboarding заново
```

**Другие возможные баги:**
- Проверить что XP начисляется правильно
- Streak считается корректно (DailyLog.date + user.streak_last_date)

### 2.3 Добавить недостающие кнопки меню

Убедиться что есть:
- "Застрял" (есть)
- "Утро" (есть)
- "Вечер" (есть)
- "Статус" (есть)
- "Изменить цель" (добавить!)

---

## Этап 3: Подготовка к деплою (1 день)

### 3.1 Настроить окружение для продакшена

**БД**: Перейти с SQLite на PostgreSQL (для Railway)

1. Установить: `pip install asyncpg`
2. Обновить `src/database/config.py`:
   ```python
   if os.getenv("DATABASE_URL"):  # Railway/prod
       TORTOISE_ORM = {..., "db_url": os.getenv("DATABASE_URL")}
   else:  # local dev
       TORTOISE_ORM = {..., "db_url": "sqlite://db.sqlite3"}
   ```
3. Добавить в env.example: `DATABASE_URL=postgres://...`

### 3.2 Настроить Railway

1. Создать проект на Railway
2. Подключить GitHub репозиторий
3. Добавить переменные окружения:
   - `BOT_TOKEN`
   - `OPENAI_KEY`
   - `DATABASE_URL` (Railway создаст автоматически если добавить PostgreSQL addon)
4. Создать Procfile:
   ```
   web: python -m src.main
   ```
5. Настроить webhook (опционально, но лучше для прода):
   ```python
   # В src/main.py
   if os.getenv("RAILWAY_ENVIRONMENT"):
       await bot.set_webhook(f"{os.getenv('RAILWAY_PUBLIC_DOMAIN')}/webhook")
   else:
       await dp.start_polling(bot)
   ```

### 3.3 Миграции

Если меняли модели:
```bash
aerich migrate --name "simplify_core"
aerich upgrade
```

На Railway это сделать через команду в настройках деплоя или в startup script.

---

## Этап 4: Деплой и первый прод-тест (1 день)

### 4.1 Деплой

1. Push в main → Railway задеплоит автоматически
2. Проверить логи: Railway Dashboard → Logs
3. Проверить что бот работает: отправить /start

### 4.2 Настроить мониторинг (минимум)

**Опции:**
- Railway Logs (бесплатно, базово)
- Sentry для ошибок (опционально)
- Простой health check: curl endpoint каждые 5 минут

### 4.3 Тест в проде

Протестировать на себе (или тестовом аккаунте):
- Полный флоу: /start → /stuck → микродействие → /evening
- Проверить что всё сохраняется в БД
- Проверить что бот не падает

---

## Этап 5: Проактивность (1 день, после стабилизации)

### 5.1 Внешний cron (как у Geo)

**Идея**: cron-job.org пингует эндпоинт каждые 2 минуты

1. Добавить эндпоинт в FastAPI:
   ```python
   @app.post("/cron/tick")
   async def cron_tick():
       # Пробежаться по юзерам
       # Проверить кому пора напоминать (по reminder_morning / reminder_evening)
       # Отправить через bot.send_message
       return {"ok": True}
   ```

2. Настроить cron-job.org:
   - URL: `https://your-railway-app.railway.app/cron/tick`
   - Interval: каждые 2 минуты
   - Method: POST

3. Логика напоминаний:
   ```python
   now = datetime.now(timezone.utc)

   # Утреннее напоминание
   for user in users:
       user_time = now + timedelta(hours=user.timezone_offset)
       if user_time.hour == 9 and user_time.minute < 2:  # reminder_morning = "09:00"
           await bot.send_message(user.telegram_id, "Доброе утро! Начнём день с микрошага?")

   # Вечернее напоминание (аналогично)
   ```

### 5.2 Альтернатива: APScheduler на сервере

Если не хочешь внешний cron:
```python
# В src/services/scheduler.py (уже есть!)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=9, minute=0)
async def morning_reminder():
    # та же логика
```

**Минус**: если Railway перезапускает сервис, schedule может сбиться.
**Плюс**: не нужен внешний сервис.

---

## Чек-лист "Ядро готово"

- [ ] Новый пользователь может: /start → ввод цели → /stuck → микродействие → отметить
- [ ] XP начисляется корректно
- [ ] Streak считается правильно
- [ ] /evening показывает итог дня
- [ ] Нет критичных багов (изменить цель, зависания)
- [ ] Бот задеплоен на Railway
- [ ] БД работает (PostgreSQL в проде)
- [ ] Webhook настроен (опционально)
- [ ] Проактивность работает (напоминания утро/вечер)
- [ ] Протестировано на себе 3-7 дней подряд

---

## Следующие шаги (ПОСЛЕ стабилизации ядра)

**Не раньше чем через 1-2 недели!**

1. **TMA фронт (Этап 6)**
   - FastAPI эндпоинты для TMA
   - Next.js фронт (2-3 экрана)
   - Vercel деплой

2. **Расширенная персонализация**
   - Вернуть квиз (упрощённый)
   - Адаптация микродействий под профиль

3. **Paywall**
   - Stripe/Телеграм Stars
   - Бесплатно: базовый режим
   - Платно: расширенная история, проактивность, дашборд

4. **Аналитика**
   - Недельная рефлексия (вернуть weekly.py)
   - Графики прогресса
   - Инсайты через AI

---

## Итоговая структура после среза

```
src/bot/handlers/
├── start.py         (~3KB)   - упрощённый старт
├── onboarding.py    (~3KB)   - прямой ввод цели
├── stuck.py         (16KB)   - ЯДРО, не трогать
├── morning.py       (~5KB)   - упрощённый AntipanicSession
├── evening.py       (~3KB)   - короткий итог
├── steps.py         (???KB)  - проверить и упростить
└── __init__.py

src/bot/states.py:
- OnboardingStates (2 состояния)
- AntipanicSession (3-4 состояния)
- StuckStates (4 состояния)
- EveningStates (2 состояния)

src/database/models.py:
- User
- Goal
- Stage (упрощённый)
- Step
- DailyLog
```

**Итого: ~35-40KB кода вместо ~70KB.**

---

## План действий по файлам (конкретика)

### День 1: Удаление и подготовка BACKLOG

1. Создать `docs/BACKLOG.md`:
   ```markdown
   # Фичи на потом (после стабилизации ядра)

   ## Квиз и онбординг-спринт
   - quiz.py (8 вопросов + AI анализ)
   - OnboardingSprintStates (paywall после микрошага)
   - QuizResult модель

   ## Еженедельная рефлексия
   - weekly.py (недельный отчёт)

   ## Health check
   - health.py (просто /health)
   ```

2. Удалить файлы:
   ```bash
   git rm src/bot/handlers/health.py
   git rm src/bot/handlers/weekly.py
   git rm src/bot/handlers/quiz.py
   ```

3. Закомментировать в `src/bot/handlers/__init__.py`:
   ```python
   # from . import quiz, weekly, health  # BACKLOG
   ```

4. Удалить из `src/bot/states.py`:
   ```python
   # class QuizStates(StatesGroup):  # BACKLOG
   # class OnboardingSprintStates(StatesGroup):  # BACKLOG
   # class GoalStates(StatesGroup):  # BACKLOG (дубль OnboardingStates)
   ```

5. Закомментировать в `src/database/models.py`:
   ```python
   # class QuizResult(models.Model):  # BACKLOG
   #     """Результат квиза перед онбордингом."""
   #     ...
   ```

### День 2: Упрощение handlers

6. Упростить `src/bot/handlers/onboarding.py`:
   - Убрать AI генерацию этапов
   - Создавать 1 дефолтный Stage
   - Убрать подтверждение

7. Упростить `src/bot/handlers/start.py`:
   - Убрать проверку QuizResult
   - Убрать сложную логику восстановления
   - Прямой путь: нет цели → onboarding

8. Упростить `src/bot/handlers/morning.py`:
   - Убрать legacy MorningStates
   - Упростить AntipanicSession до 3-4 состояний

9. Упростить `src/bot/handlers/evening.py`:
   - Убрать детализацию причин пропуска
   - Короткий итог: что сделано + XP + streak

10. Проверить `src/bot/handlers/steps.py`:
    - Прочитать полностью
    - Удалить избыточное
    - Оставить только: отметить done/skip

### День 3: Тестирование и фиксы

11. Тест нового пользователя
12. Тест повторного дня
13. Тест застревания
14. Добавить кнопку "Изменить цель"
15. Исправить баги

### День 4: Деплой

16. Настроить PostgreSQL
17. Создать Railway проект
18. Настроить переменные окружения
19. Деплой
20. Тест в проде

### День 5+: Проактивность и стабилизация

21. Внешний cron или APScheduler
22. Напоминания утро/вечер
23. Тест на себе 3-7 дней
24. Собрать фидбек

---

## Контрольные вопросы перед стартом

**Q1**: Готов ли ты удалить quiz.py и потерять эту фичу на 2-4 недели?
**A1**: Да, потому что прямой старт = меньше трения, быстрее к микродействию.

**Q2**: Готов ли ты упростить onboarding (без AI генерации этапов)?
**A2**: Да, потому что 1 дефолтный этап = работает, AI этапы = можно вернуть потом.

**Q3**: Нужна ли сейчас структура Goal → Stage → Step или можно Goal → Step?
**A3**: Оставить Stage, но не усложнять. Просто 1 дефолтный активный Stage.

**Q4**: Как будешь тестировать ядро?
**A4**: На себе, 3-7 дней подряд, до деплоя.

**Q5**: Что делать если в процессе среза что-то сломается?
**A5**: Git branch для среза, коммиты часто, можно откатиться.

---

## Git strategy

```bash
# Создать ветку для среза
git checkout -b feature/core-reduction

# Коммитить каждый шаг
git commit -m "chore: move quiz/weekly/health to BACKLOG"
git commit -m "refactor: simplify onboarding (remove AI stage generation)"
git commit -m "refactor: simplify start.py (direct path to onboarding)"
# ...

# После тестов
git checkout main
git merge feature/core-reduction
git push origin main
```

---

**НАЧИНАЕМ?**

Если да, то первое действие:
```bash
# 1. Создать BACKLOG.md
# 2. Удалить health.py, weekly.py
# 3. Закомментировать quiz.py импорт
# 4. Коммит: "chore: move non-core features to BACKLOG"
```
