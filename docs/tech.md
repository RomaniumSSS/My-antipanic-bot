# Antipanic Bot — Техническая документация

## Стек

- Python 3.11+
- aiogram 3.x
- Tortoise ORM + SQLite
- OpenAI API (GPT-4o)
- APScheduler (напоминания)

## Структура

```
src/
├── main.py              # Точка входа
├── config.py            # Настройки из .env
├── bot/
│   ├── handlers/        # Роутеры (start, morning, stuck, evening)
│   ├── states.py        # FSM состояния
│   └── keyboards.py     # Клавиатуры
├── database/
│   ├── config.py        # Tortoise config
│   └── models.py        # User, Goal, Stage, Step, DailyLog
└── services/
    └── ai.py            # OpenAI wrapper
```

## Модели

- **User**: telegram_id, xp, level, streak, настройки напоминаний
- **Goal**: цель с дедлайном
- **Stage**: этап цели (2-4 на цель)
- **Step**: шаг с difficulty (easy/medium/hard) и estimated_minutes
- **DailyLog**: дневник дня (энергия, состояние, что сделано)

## FSM Flows

1. **Onboarding**: goal → deadline → confirm stages
2. **Morning**: energy (1-10) → mood (text) → show steps
3. **Stuck**: blocker type → details → microhit
4. **Evening**: mark done → skip reasons → rating

## Запуск

```bash
cd antipanic-bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
# создай .env с BOT_TOKEN и OPENAI_KEY
python -m src.main
```

## OpenCommit (AI коммиты)

- Dev-зависимость `opencommit` добавлена; скрипты: `npm run oc`, `npm run oc:hook`, `npm run oc:hook:unset`.
- Скопируй `opencommit.env.example` в `.env` и задай `OCO_API_KEY` (OpenAI) и при необходимости `OCO_MODEL`, `OCO_LANGUAGE`.
- Для автоматической подстановки в Git hook выполни `npm run oc:hook` внутри репозитория.
- Использование: проиндексируй изменения (`git add ...`), запусти `npm run oc` — получишь сгенерированное сообщение коммита с возможностью подтвердить/отредактировать.