# Antipanic Bot — Техническая документация

## Архитектура
Асинхронный Telegram-бот на aiogram 3.x. Бизнес-флоу реализованы в роутерах (FSM), данные хранятся через Tortoise ORM + SQLite, напоминания — APScheduler, генерация шагов и микро-ударов — OpenAI GPT-4o.

## Стек
- Python 3.11+  
- aiogram 3.x  
- Tortoise ORM + SQLite  
- OpenAI API (GPT-4o)  
- APScheduler (напоминания)

## Структура проекта
```
src/
├── main.py              # Точка входа
├── config.py            # Настройки из .env
├── bot/
│   ├── handlers/        # Роутеры (start, quiz, morning, stuck, evening)
│   ├── callbacks/       # CallbackData фабрики
│   │   └── data.py      # EnergyCallback, BlockerCallback, etc.
│   ├── middlewares/     # Middleware (access, etc.)
│   ├── states.py        # FSM состояния
│   └── keyboards.py     # Клавиатуры (используют callbacks/data.py)
├── interfaces/
│   └── api/             # FastAPI TMA endpoints
│       ├── main.py      # FastAPI app с CORS
│       ├── auth.py      # Telegram WebApp initData валидация
│       ├── schemas.py   # Pydantic модели ответов
│       └── routers/     # API роутеры (/api/me, /api/goals, etc.)
├── database/
│   ├── config.py        # Tortoise config
│   └── models.py        # User, Goal, Stage, Step, DailyLog
└── services/
    ├── ai.py            # OpenAI wrapper
    └── scheduler.py     # APScheduler wrapper
```

## Модели данных
- **User**: telegram_id, xp, level, streak, настройки напоминаний  
- **Goal**: цель с дедлайном  
- **Stage**: этап цели (2-4 на цель)  
- **Step**: шаг с difficulty (easy/medium/hard) и estimated_minutes  
- **DailyLog**: дневник дня (энергия, состояние, что сделано)  
- **QuizResult**: ответы квиза, dependency_score, AI-диагноз, completed_at

## Бот-флоу (FSM)
1. **Quiz**: 10 вопросов → dependency_score → AI-диагноз → мини-спринт + пейволл  
2. **Onboarding**: goal → deadline → confirm stages  
3. **Morning**: energy (1-10) → mood (text) → show steps  
4. **Stuck**: blocker type → details → microhit  
5. **Evening**: mark done → skip reasons → rating

## Интеграции
- Telegram Bot API через aiogram.  
- OpenAI GPT-4o через `services/ai.py`.  
- APScheduler — планировщик напоминаний (локально).
- FastAPI — REST API для Telegram Mini App (TMA).

## TMA API Endpoints
REST API для фронтенда Telegram Mini App (см. `src/interfaces/api/`):

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/me` | GET | Профиль пользователя |
| `/api/goals` | GET | Список целей |
| `/api/goals/{id}` | GET | Детали цели со стадиями |
| `/api/stats` | GET | Статистика (XP, streak, прогресс) |
| `/api/microhit` | POST | Генерация микро-действия |
| `/api/health` | GET | Health check API |
| `/api/docs` | GET | Swagger документация |

**Аутентификация**: Header `Authorization: tma <initData>` — валидация через HMAC-SHA256.

## Конфигурация и запуск
- Переменные окружения: `BOT_TOKEN`, `OPENAI_KEY`.  
- Шаги:
```bash
cd antipanic-bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

## Безопасность и качество
- Токены только из окружения; не коммитить секреты.  
- Данные пользователей — в локальной SQLite; при выносе в облако добавить шифрование/бэкапы.  
- Логи не должны содержать персональные данные.

## Dev tools — OpenCommit (AI коммиты)
- Dev-зависимость `opencommit`; скрипты: `npm run oc`, `npm run oc:hook`, `npm run oc:hook:unset`.  
- Скопируй `opencommit.env.example` в `.env`, задай `OCO_API_KEY` (и опционально `OCO_MODEL`, `OCO_LANGUAGE`).  
- Для Git hook: `npm run oc:hook`. Использование: `git add ...`, затем `npm run oc` — сгенерирует сообщение коммита для подтверждения/правки.