# План миграции Antipanic Bot в Telegram Mini App

**Дата**: 2025-12-12
**Цель**: Перенести бота в TMA, сохранив Python бэкенд
**Проблема**: Страх и ступор → бездействие
**Решение**: Telegram Mini App с проактивностью и геймификацией

---

## Главная идея

**Сейчас**: Telegram бот на Python (aiogram) + SQLite
**Будет**:
- **Бот** (Python/aiogram на Railway) — остаётся для уведомлений и быстрого доступа
- **TMA фронт** (Next.js на Vercel) — основной интерфейс
- **API** (FastAPI на Railway) — бизнес-логика для TMA
- **БД** (PostgreSQL на Railway/Supabase) — общая для бота и TMA
- **Проактивность** (внешний cron или APScheduler) — напоминания

**Почему это работает**:
- TMA = веб-интерфейс, красивый и удобный
- Бот = уведомления и точка входа
- Python бэкенд = твоя логика остаётся, не переписывать всё на JS
- Разделение слоёв = можно развивать независимо

---

## Весь путь в 5 этапах (2-4 недели)

```
Этап 1: Срезать дерево до ядра (2-3 дня)
  └→ Оставить только: ступор → микродействие → XP → итог

Этап 2: Разделить слои (2-3 дня)
  └→ core/ storage/ interfaces/bot/ interfaces/api/

Этап 3: Деплой бота + БД (1-2 дня)
  └→ Railway + PostgreSQL + webhook

Этап 4: TMA MVP (3-5 дней)
  └→ FastAPI (6 эндпоинтов) + Next.js (3 экрана)

Этап 5: Проактивность (1 день)
  └→ Внешний cron → напоминания
```

---

## Этап 1: Срезать дерево до ядра (2-3 дня)

**Цель**: Понять ЧТО переносить в TMA

### Зачем срезать перед переносом?

Если переносить всё "как есть" (quiz, weekly, health, сложный onboarding) → утонешь в багах и поддержке.

**Правило**: Сначала переноси **меню/ядро**, потом добавляй фичи.

### Что оставить (минимальное ядро)

1. **Onboarding** (упрощённый)
   - Ввод цели → создание Goal + 1 дефолтный Stage
   - Без AI генерации этапов (отложить)

2. **Stuck flow** (ЯДРО!)
   - Выбор блокера → AI микроудар → фидбек
   - Это главная ценность, не трогать

3. **Morning/Antipanic** (упрощённый)
   - Замер напряжения → микродействие → выполнение
   - Убрать лишние состояния

4. **Evening** (минимум)
   - Показать что сделано → отметить → XP + streak

5. **XP + streak** (геймификация)
   - User.xp, User.level, User.streak_days
   - DailyLog для истории

6. **Базовые модели**
   - User, Goal, Stage (упрощённый), Step, DailyLog

### Что удалить/заморозить (в BACKLOG.md)

- `quiz.py` (10KB) — отложить, сделать прямой старт
- `weekly.py` (5KB) — отложить
- `health.py` (359B) — удалить
- `OnboardingSprintStates` (paywall) — отложить
- `QuizResult` модель — удалить

### Что упростить

- **onboarding.py**: 8KB → 3KB (без AI этапов)
- **start.py**: 6.4KB → 3KB (без квиза)
- **morning.py**: 10KB → 5KB (только AntipanicSession, без legacy)
- **evening.py**: 7KB → 3KB (короткий итог)

### Действия

1. Создать `docs/BACKLOG.md`
2. Удалить файлы: `health.py`, `weekly.py`
3. Закомментировать `quiz.py` импорт
4. Упростить handlers (см. детали в `/docs/CORE_REDUCTION_PLAN.md`)
5. Тест вручную: новый пользователь → цель → /stuck → микродействие → /evening
6. Исправить баг "изменить цель" (добавить команду)

**Результат**: Стабильное ядро ~35-40KB кода вместо ~70KB

**Файл с деталями**: `/docs/CORE_REDUCTION_PLAN.md` (уже создан)

---

## Этап 2: Разделить слои (2-3 дня)

**Цель**: Подготовить код для TMA, разделить бот и логику

### Зачем разделять слои?

**Проблема**: Сейчас вся логика в aiogram handlers → нельзя подключить TMA без дублирования кода.

**Решение**: Разделить на слои:
```
src/
├── core/              # Бизнес-логика (без зависимости от aiogram/fastapi)
│   ├── actions.py     # Создание микродействий
│   ├── gamification.py # XP, streak, level
│   ├── stuck_logic.py # Логика микроударов
│   └── daily_log.py   # Работа с DailyLog
├── storage/           # Работа с БД (репозитории)
│   ├── user_repo.py
│   ├── goal_repo.py
│   ├── step_repo.py
│   └── daily_log_repo.py
├── interfaces/
│   ├── bot/           # aiogram handlers (кнопки/команды)
│   │   ├── handlers/
│   │   ├── keyboards.py
│   │   └── states.py
│   └── api/           # FastAPI эндпоинты (для TMA)
│       ├── routers/
│       └── schemas.py
├── services/
│   ├── ai.py          # OpenAI
│   └── scheduler.py   # APScheduler
├── database/
│   ├── models.py
│   └── config.py
└── main.py            # Точка входа бота
```

### Принцип разделения

**Правило**: aiogram handler НЕ должен содержать бизнес-логику, только:
1. Получить данные от пользователя
2. Вызвать `core` функцию
3. Отправить результат пользователю

**Было** (плохо):
```python
# src/bot/handlers/stuck.py
@router.callback_query(...)
async def blocker_other(callback: CallbackQuery, ...):
    blocker_type = callback_data.type

    # ❌ Бизнес-логика прямо в handler
    microhit = await ai_service.get_microhit(...)
    step.status = "completed"
    await step.save()
    user.xp += step.xp_reward
    await user.save()

    await callback.message.edit_text(...)
```

**Стало** (хорошо):
```python
# src/core/stuck_logic.py
async def generate_microhit(
    step_title: str,
    blocker_type: str,
    details: str = ""
) -> str:
    """Бизнес-логика генерации микроудара."""
    return await ai_service.get_microhit(step_title, blocker_type, details)

async def complete_microhit(user_id: int, step_id: int) -> dict:
    """Отметить микроудар выполненным и начислить XP."""
    user = await user_repo.get_by_telegram_id(user_id)
    step = await step_repo.get_by_id(step_id)

    step.status = "completed"
    await step_repo.save(step)

    xp_earned = await gamification.add_xp(user, step.xp_reward)

    return {"xp_earned": xp_earned, "total_xp": user.xp}

# src/interfaces/bot/handlers/stuck.py
@router.callback_query(...)
async def blocker_other(callback: CallbackQuery, ...):
    # ✅ Только вызов core и отображение
    microhit = await stuck_logic.generate_microhit(
        step_title=...,
        blocker_type=...,
    )
    await callback.message.edit_text(f"💡 {microhit}")
```

Теперь **FastAPI эндпоинт для TMA** может использовать ТУ ЖЕ логику:
```python
# src/interfaces/api/routers/stuck.py
@router.post("/microhit/generate")
async def generate_microhit_api(data: MicrohitRequest):
    microhit = await stuck_logic.generate_microhit(
        step_title=data.step_title,
        blocker_type=data.blocker_type,
    )
    return {"microhit": microhit}
```

### Что переместить

1. **core/actions.py**
   - Создание микродействий
   - Генерация шагов через AI
   - Логика AntipanicSession

2. **core/gamification.py**
   - `add_xp(user, amount) -> int`
   - `update_streak(user) -> int`
   - `calculate_level(xp) -> int`

3. **core/stuck_logic.py**
   - `generate_microhit(...) -> str`
   - `complete_microhit(...) -> dict`
   - `get_blocker_options() -> list`

4. **core/daily_log.py**
   - `create_or_get_today_log(user) -> DailyLog`
   - `add_step_to_log(log, step, completed=False)`
   - `get_day_summary(user, date) -> dict`

5. **storage/** (репозитории)
   - Все операции с БД через репозитории
   - `user_repo.get_by_telegram_id(id)`
   - `goal_repo.get_active_for_user(user)`
   - `step_repo.create(stage, data)`

### Действия

1. Создать структуру папок `core/` и `storage/`
2. Вынести логику из handlers в core
3. Обернуть все обращения к БД в репозитории
4. Обновить handlers: убрать логику, оставить только вызовы core
5. Тест: убедиться что бот работает так же
6. Коммит: `refactor: extract business logic to core layer`

**Результат**: Логика отделена от интерфейса, готова к подключению API

---

## Этап 3: Деплой бота + БД (1-2 дня)

**Цель**: Вывести бота в прод, чтобы работал 24/7

### Почему сейчас?

- Ядро стабильно (Этап 1)
- Логика отделена (Этап 2)
- Перед TMA нужно чтобы бот уже работал в проде

### Выбор стека

**БД**: PostgreSQL (Railway или Supabase)
- Railway: всё в одном месте (бот + БД)
- Supabase: бесплатный tier, хорошо для старта (как у Geo)

**Хостинг бота**: Railway
- Бесплатный tier: $5 credit/месяц
- Webhook поддержка
- Автодеплой из GitHub

**Альтернативы**: Render, Fly.io, AWS (сложнее)

### Настройка PostgreSQL

1. **Если Railway**:
   - Создать проект → Add service → PostgreSQL
   - Скопировать `DATABASE_URL` из переменных

2. **Если Supabase** (как у Geo):
   - Зарегистрироваться на supabase.com
   - Создать проект → Settings → Database
   - Скопировать Connection String (URI)

3. **Обновить код**:
   ```python
   # src/database/config.py
   import os

   DATABASE_URL = os.getenv("DATABASE_URL", "sqlite://db.sqlite3")

   # Для Railway нужно заменить postgres:// на postgresql://
   if DATABASE_URL.startswith("postgres://"):
       DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

   TORTOISE_ORM = {
       "connections": {"default": DATABASE_URL},
       "apps": {
           "models": {
               "models": ["src.database.models", "aerich.models"],
               "default_connection": "default",
           }
       },
   }
   ```

4. **Установить драйвер**:
   ```bash
   pip install asyncpg
   # Добавить в requirements.txt
   ```

### Настройка Railway

1. **Создать проект**:
   - railway.app → New Project → Deploy from GitHub repo
   - Выбрать репозиторий

2. **Добавить переменные окружения**:
   - `BOT_TOKEN` — токен бота
   - `OPENAI_KEY` — ключ OpenAI
   - `DATABASE_URL` — из PostgreSQL сервиса Railway
   - `ENVIRONMENT` — `production`

3. **Настроить webhook** (опционально, но лучше для прода):
   ```python
   # src/main.py
   import os

   async def main():
       # ... init bot, dp ...

       if os.getenv("ENVIRONMENT") == "production":
           # Webhook для прода
           webhook_url = f"https://{os.getenv('RAILWAY_PUBLIC_DOMAIN')}/webhook"
           await bot.set_webhook(webhook_url)

           # Запустить aiohttp для приёма webhook
           from aiohttp import web

           async def handle_webhook(request):
               update = await request.json()
               await dp.feed_webhook_update(bot, update)
               return web.Response()

           app = web.Application()
           app.router.add_post("/webhook", handle_webhook)
           web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
       else:
           # Polling для локалки
           await dp.start_polling(bot)
   ```

4. **Deploy**:
   - Railway задеплоит автоматически при push в main
   - Проверить логи: Dashboard → Deployments → Logs

### Миграции БД

```bash
# Локально
aerich init -t src.database.config.TORTOISE_ORM
aerich init-db

# На Railway (через startup script или вручную)
# Добавить в railway.json:
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "aerich upgrade && python -m src.main"
  }
}
```

### Тест в проде

1. Отправить /start боту
2. Пройти флоу: цель → /stuck → микродействие
3. Проверить что данные сохраняются в БД
4. Проверить логи Railway: нет ошибок

**Результат**: Бот работает 24/7 на Railway + PostgreSQL

---

## Этап 4: TMA MVP (3-5 дней)

**Цель**: Создать минимальный TMA интерфейс (3 экрана)

### Архитектура TMA

```
┌─────────────────┐
│  Telegram User  │
└────────┬────────┘
         │
    ┌────▼─────┐
    │   Bot    │ (кнопка "Открыть App")
    └────┬─────┘
         │
    ┌────▼─────────────────┐
    │  TMA (Next.js)       │ ← Vercel
    │  - Home              │
    │  - Stuck flow        │
    │  - Stats             │
    └────┬─────────────────┘
         │ HTTP
    ┌────▼─────────────────┐
    │  FastAPI             │ ← Railway
    │  - /me               │
    │  - /microhit/*       │
    │  - /stats            │
    └────┬─────────────────┘
         │
    ┌────▼─────────────────┐
    │  PostgreSQL          │ ← Railway/Supabase
    └──────────────────────┘
```

### Шаг 4.1: FastAPI (Python бэкенд для TMA)

**Структура API**:
```
src/interfaces/api/
├── main.py           # FastAPI app
├── auth.py           # Telegram auth validation
├── schemas.py        # Pydantic модели
└── routers/
    ├── user.py       # GET /me
    ├── microhit.py   # POST /microhit/generate, /microhit/complete
    └── stats.py      # GET /stats
```

**Минимальные эндпоинты** (6 штук):

1. **GET /me** — профиль пользователя
   ```python
   {
     "telegram_id": 123456,
     "username": "user",
     "xp": 150,
     "level": 2,
     "streak_days": 5
   }
   ```

2. **GET /goals** — активная цель
   ```python
   {
     "id": 1,
     "title": "Выучить Python",
     "current_stage": "Начало",
     "progress": 30
   }
   ```

3. **POST /microhit/generate** — сгенерировать микроудар
   ```python
   # Request
   {
     "step_title": "Написать функцию",
     "blocker_type": "fear",
     "details": ""
   }

   # Response
   {
     "microhit": "Открой редактор и напиши заголовок функции def calculate():",
     "step_id": 42
   }
   ```

4. **POST /microhit/complete** — отметить выполненным
   ```python
   # Request
   {"step_id": 42}

   # Response
   {
     "xp_earned": 10,
     "total_xp": 160,
     "streak_days": 5
   }
   ```

5. **GET /stats** — статистика
   ```python
   {
     "today": {
       "energy_level": 7,
       "steps_assigned": 3,
       "steps_completed": 2,
       "xp_earned": 20
     },
     "week": {
       "active_days": 5,
       "total_xp": 150,
       "total_steps": 12
     }
   }
   ```

6. **GET /history** — история шагов
   ```python
   {
     "steps": [
       {
         "id": 42,
         "title": "Написать функцию",
         "completed_at": "2025-12-12T10:30:00Z",
         "xp_reward": 10
       },
       ...
     ]
   }
   ```

**Код примера** (`src/interfaces/api/main.py`):
```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.interfaces.api import auth, schemas
from src.interfaces.api.routers import user, microhit, stats
from src.database.config import init_db

app = FastAPI(title="Antipanic API")

# CORS для Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-tma.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router, prefix="/api", tags=["user"])
app.include_router(microhit.router, prefix="/api", tags=["microhit"])
app.include_router(stats.router, prefix="/api", tags=["stats"])

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/")
async def root():
    return {"status": "ok"}
```

**Telegram Auth** (`src/interfaces/api/auth.py`):
```python
from fastapi import Header, HTTPException
import hashlib
import hmac

from src.config import settings

def verify_telegram_auth(init_data: str) -> dict:
    """
    Проверяет подпись initData от Telegram WebApp.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    # Парсинг initData
    params = dict(param.split("=") for param in init_data.split("&"))
    hash_value = params.pop("hash", None)

    if not hash_value:
        raise HTTPException(401, "Missing hash")

    # Проверка подписи
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new("WebAppData".encode(), settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if calculated_hash != hash_value:
        raise HTTPException(401, "Invalid hash")

    return params

async def get_current_user(x_telegram_init_data: str = Header(...)):
    """Dependency для получения текущего юзера из Telegram auth."""
    params = verify_telegram_auth(x_telegram_init_data)
    user_data = json.loads(params.get("user", "{}"))

    from src.storage.user_repo import get_by_telegram_id
    user = await get_by_telegram_id(user_data["id"])

    if not user:
        raise HTTPException(404, "User not found")

    return user
```

**Роутер пример** (`src/interfaces/api/routers/microhit.py`):
```python
from fastapi import APIRouter, Depends

from src.interfaces.api import schemas
from src.interfaces.api.auth import get_current_user
from src.core import stuck_logic
from src.database.models import User

router = APIRouter()

@router.post("/microhit/generate", response_model=schemas.MicrohitResponse)
async def generate_microhit(
    data: schemas.MicrohitRequest,
    user: User = Depends(get_current_user)
):
    microhit = await stuck_logic.generate_microhit(
        step_title=data.step_title,
        blocker_type=data.blocker_type,
        details=data.details or ""
    )

    # Создать step для этого микроудара
    step = await stuck_logic.create_microhit_step(user, data.step_title, microhit)

    return {
        "microhit": microhit,
        "step_id": step.id
    }

@router.post("/microhit/complete", response_model=schemas.CompleteResponse)
async def complete_microhit(
    data: schemas.CompleteRequest,
    user: User = Depends(get_current_user)
):
    result = await stuck_logic.complete_microhit(user.telegram_id, data.step_id)
    return result
```

**Деплой API на Railway**:
1. Добавить в `src/main.py` запуск FastAPI вместе с ботом:
   ```python
   # Опция 1: Два отдельных сервиса на Railway
   # - Service 1: python -m src.main (бот)
   # - Service 2: uvicorn src.interfaces.api.main:app (API)

   # Опция 2 (проще): Один сервис, API и бот вместе
   # Использовать webhook + FastAPI в одном процессе
   ```

2. Railway → Add Service → выбрать тот же репозиторий
3. Start Command: `uvicorn src.interfaces.api.main:app --host 0.0.0.0 --port $PORT`
4. Получить URL: `https://your-api.railway.app`

### Шаг 4.2: TMA Фронт (Next.js на Vercel)

**Структура проекта**:
```
antipanic-tma/          # Отдельный репозиторий
├── src/
│   ├── app/
│   │   ├── page.tsx           # Home
│   │   ├── stuck/page.tsx     # Stuck flow
│   │   └── stats/page.tsx     # Stats
│   ├── components/
│   │   ├── MicrohitCard.tsx
│   │   ├── StatsWidget.tsx
│   │   └── BottomNav.tsx
│   ├── lib/
│   │   ├── api.ts             # Axios client
│   │   └── telegram.ts        # Telegram WebApp SDK
│   └── types/
│       └── index.ts
├── public/
├── package.json
└── next.config.js
```

**Минимальные экраны** (3 штуки):

1. **Home** (`/`)
   - Приветствие
   - Текущая цель + прогресс
   - Кнопка "Застрял?" → /stuck
   - XP + streak виджет

2. **Stuck flow** (`/stuck`)
   - Выбор блокера (4 кнопки)
   - Генерация микроудара (loading)
   - Показ микроудара
   - Кнопки: "Сделано" / "Ещё вариант" / "Другое"

3. **Stats** (`/stats`)
   - Сегодня: энергия, шаги, XP
   - Неделя: активные дни, общий XP
   - История последних шагов

**Код примера** (`src/app/page.tsx`):
```typescript
'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { initTelegramWebApp } from '@/lib/telegram';

export default function Home() {
  const [user, setUser] = useState(null);
  const [goal, setGoal] = useState(null);

  useEffect(() => {
    const tg = initTelegramWebApp();

    // Загрузить профиль
    api.get('/me').then(res => setUser(res.data));
    api.get('/goals').then(res => setGoal(res.data));
  }, []);

  if (!user) return <div>Loading...</div>;

  return (
    <div className="container">
      <h1>Привет, {user.username}!</h1>

      {goal && (
        <div className="goal-card">
          <h2>{goal.title}</h2>
          <progress value={goal.progress} max={100} />
          <p>{goal.current_stage}</p>
        </div>
      )}

      <div className="stats">
        <div>XP: {user.xp}</div>
        <div>Level: {user.level}</div>
        <div>Streak: {user.streak_days} дней</div>
      </div>

      <button onClick={() => window.location.href = '/stuck'}>
        Застрял?
      </button>
    </div>
  );
}
```

**Telegram WebApp SDK** (`src/lib/telegram.ts`):
```typescript
export function initTelegramWebApp() {
  const tg = (window as any).Telegram.WebApp;
  tg.ready();
  tg.expand();
  return tg;
}

export function getInitData(): string {
  const tg = (window as any).Telegram.WebApp;
  return tg.initData;
}
```

**API Client** (`src/lib/api.ts`):
```typescript
import axios from 'axios';
import { getInitData } from './telegram';

export const api = axios.create({
  baseURL: 'https://your-api.railway.app/api',
  headers: {
    'X-Telegram-Init-Data': getInitData()
  }
});
```

**Деплой на Vercel**:
1. Создать репозиторий `antipanic-tma`
2. Push код
3. vercel.com → Import Project → выбрать репозиторий
4. Deploy
5. Получить URL: `https://antipanic-tma.vercel.app`

### Шаг 4.3: Подключить TMA к боту

**В BotFather**:
1. /mybots → выбрать бота → Menu Button
2. Set Menu Button URL: `https://antipanic-tma.vercel.app`

**Или через код**:
```python
await bot.set_chat_menu_button(
    menu_button=types.MenuButtonWebApp(
        text="Открыть App",
        web_app=types.WebAppInfo(url="https://antipanic-tma.vercel.app")
    )
)
```

**Тест**:
1. Открыть бота в Telegram
2. Нажать кнопку Menu (≡) внизу
3. Откроется TMA в браузере внутри Telegram
4. Проверить что работает: Home → Stuck → Stats

**Результат**: TMA MVP работает, подключён к боту, использует Python API

---

## Этап 5: Проактивность (1 день)

**Цель**: Напоминания утром/вечером (как у Geo)

### Способ 1: Внешний cron (как у Geo)

**Почему Geo выбрал это**:
- Не зависит от перезапусков сервера
- Простая отладка (просто пингуешь endpoint)
- Бесплатный tier на cron-job.org

**Как работает**:
```
cron-job.org (каждые 2 минуты)
  → POST https://your-api.railway.app/cron/tick
    → проверить кому пора напоминать
      → отправить через bot.send_message
```

**Код** (`src/interfaces/api/routers/cron.py`):
```python
from fastapi import APIRouter, Header, HTTPException
from datetime import datetime, timedelta, timezone

from src.database.models import User
from src.config import settings

router = APIRouter()

# Секретный токен для защиты endpoint
CRON_SECRET = settings.CRON_SECRET

@router.post("/cron/tick")
async def cron_tick(x_cron_secret: str = Header(...)):
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(401, "Invalid secret")

    now = datetime.now(timezone.utc)
    users = await User.all()

    reminders_sent = 0

    for user in users:
        # Считаем локальное время юзера
        user_time = now + timedelta(hours=user.timezone_offset)
        hour = user_time.hour
        minute = user_time.minute

        # Утреннее напоминание (09:00)
        morning_hour = int(user.reminder_morning.split(":")[0])
        if hour == morning_hour and minute < 2:  # окно 2 минуты
            # Проверить что не отправляли сегодня
            if not await already_sent_today(user, "morning"):
                await send_morning_reminder(user)
                reminders_sent += 1

        # Вечернее напоминание (21:00)
        evening_hour = int(user.reminder_evening.split(":")[0])
        if hour == evening_hour and minute < 2:
            if not await already_sent_today(user, "evening"):
                await send_evening_reminder(user)
                reminders_sent += 1

    return {"reminders_sent": reminders_sent}

async def send_morning_reminder(user: User):
    from src.main import bot  # Импорт бота

    await bot.send_message(
        user.telegram_id,
        "🌅 Доброе утро! Начнём день с микрошага?\n\n"
        "Жми /morning или открой App"
    )

async def send_evening_reminder(user: User):
    from src.main import bot

    await bot.send_message(
        user.telegram_id,
        "🌙 Время подвести итог дня!\n\n"
        "Что успел сделать? Жми /evening"
    )
```

**Настройка cron-job.org**:
1. Зарегистрироваться на cron-job.org (бесплатно)
2. Create Cronjob:
   - URL: `https://your-api.railway.app/api/cron/tick`
   - Method: POST
   - Headers: `X-Cron-Secret: your-secret-token`
   - Schedule: Every 2 minutes
3. Save & Start

**Важно**: Добавить в Railway переменную `CRON_SECRET`

### Способ 2: APScheduler на сервере

```python
# src/services/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta, timezone

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", minute="*/2")
async def check_reminders():
    # Та же логика что в cron endpoint
    pass

# В src/main.py
@dp.startup()
async def on_startup():
    scheduler.start()

@dp.shutdown()
async def on_shutdown():
    scheduler.shutdown()
```

**Минус**: Если Railway перезапустит сервис в 8:59, то напоминание в 9:00 может пропасть.

**Плюс**: Не нужен внешний сервис.

**Рекомендация**: Начни с внешнего cron (как у Geo), проще отлаживать.

**Результат**: Пользователи получают напоминания утром и вечером

---

## Чек-лист "TMA готово"

- [ ] **Этап 1**: Ядро срезано, бот стабилен
- [ ] **Этап 2**: Логика вынесена в core/, репозитории работают
- [ ] **Этап 3**: Бот задеплоен на Railway + PostgreSQL
- [ ] **Этап 4.1**: FastAPI работает, 6 эндпоинтов отвечают
- [ ] **Этап 4.2**: TMA фронт на Vercel, 3 экрана работают
- [ ] **Этап 4.3**: TMA подключён к боту, кнопка Menu работает
- [ ] **Этап 5**: Проактивность настроена, напоминания приходят
- [ ] Протестировано на себе 3-7 дней
- [ ] Нет критичных багов

---

## Следующие шаги (после TMA MVP)

**Не раньше чем через 2-3 недели!**

### 1. Paywall и монетизация
- Stripe/Телеграм Stars
- Бесплатно: базовый режим, ограниченная история
- Платно: расширенная история, проактивность, дашборд, персонализация

### 2. Расширенный TMA
- Дашборд с графиками (Chart.js/Recharts)
- История за месяц/год
- Настройки напоминаний через TMA
- Смена целей через TMA

### 3. Вернуть фичи из BACKLOG
- Квиз (упрощённый, 3-4 вопроса)
- Недельная рефлексия
- AI генерация этапов для целей

### 4. Улучшения AI
- Персонализация микроударов под профиль
- Анализ паттернов прокрастинации
- Инсайты и рекомендации

### 5. Социальные фичи
- Sharing прогресса (Telegram Stories)
- Referral program
- Community челленджи

---

## Время и усилия (реально)

**При условии что работаешь 2-3 часа в день**:

| Этап | Описание | Время |
|------|----------|-------|
| 1 | Срезать дерево до ядра | 2-3 дня |
| 2 | Разделить слои (core/storage/interfaces) | 2-3 дня |
| 3 | Деплой бота + БД | 1-2 дня |
| 4 | TMA MVP (API + фронт) | 3-5 дней |
| 5 | Проактивность | 1 день |
| **Итого** | **От старта до TMA в проде** | **9-14 дней** |

**Если работаешь по 5-8 часов в день**: можно за **5-7 дней**.

**Как у Geo**: он сделал за **1 день** (перенос в TMA), но у него:
- Уже было ядро стабильное
- Меню/кнопки в боте = легко портировать в TMA
- Опыт с Next.js и Supabase

Ты будешь чуть медленнее, потому что:
- Нужно срезать дерево (у тебя больше фич)
- Python + FastAPI (нужно разделить слои)
- Первый раз TMA (обучение)

Но это нормально! Главное — делать по этапам, не спешить.

---

## Что делать если застрянешь

### Проблема 1: "Слишком много кода, не знаю с чего начать"
**Решение**: Начни с Этапа 1, день 1:
1. Создай BACKLOG.md
2. Удали health.py и weekly.py
3. Коммит
4. Следующий день — упрости onboarding.py

### Проблема 2: "Боюсь сломать что-то при выносе в core/"
**Решение**:
1. Создай ветку `feature/core-refactor`
2. Выноси по одному файлу за раз
3. Тестируй после каждого выноса
4. Коммитируй часто

### Проблема 3: "TMA не подключается к API (CORS/auth ошибки)"
**Решение**:
1. Проверь CORS: `allow_origins` включает твой Vercel домен
2. Проверь Telegram auth: логируй `initData` на фронте и бэке
3. Тестируй локально сначала: ngrok для API, localhost для TMA

### Проблема 4: "Не понимаю как работает Telegram WebApp SDK"
**Решение**:
1. Прочитай доку: https://core.telegram.org/bots/webapps
2. Используй примеры: https://github.com/telegram-mini-apps
3. Начни с простого: просто покажи `initData` на экране

### Проблема 5: "Railway дорого, не хватает бесплатного tier"
**Решение**:
1. Используй Render (бесплатный tier, но медленнее)
2. Supabase для БД (бесплатный tier 500MB)
3. Vercel для фронта (бесплатно)
4. cron-job.org для напоминаний (бесплатно)
Итого: можно полностью бесплатно до первых 100 пользователей

---

## Git strategy

```bash
# Основная ветка
main (продакшен)

# Ветки для этапов
feature/core-reduction    # Этап 1
feature/layer-separation  # Этап 2
feature/railway-deploy    # Этап 3
feature/tma-api           # Этап 4.1
feature/tma-frontend      # Этап 4.2
feature/proactivity       # Этап 5

# Workflow
1. Создать ветку для этапа
2. Коммитить часто (каждое изменение)
3. После завершения этапа: тест вручную
4. Merge в main
5. Деплой
6. Тест в проде
7. Следующий этап
```

---

## Вопросы для уточнения перед стартом

1. **Готов ли ты удалить quiz.py и weekly.py?** (можно вернуть потом)
2. **Какой БД выбираешь: Railway PostgreSQL или Supabase?**
3. **Есть ли опыт с Next.js/React?** (если нет — будет +1-2 дня на обучение)
4. **Когда планируешь начать?** (чтобы я мог помочь в процессе)
5. **Сколько часов в день готов работать?** (для оценки времени)

---

**ГОТОВ НАЧИНАТЬ?**

Если да, то:
1. Скажи "начинаем" → я создам ветку и начну Этап 1, день 1
2. Если нужны уточнения — задавай вопросы по плану
3. Если хочешь изменить что-то в плане — говори

Я готов помочь на каждом этапе! 🚀
