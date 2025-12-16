# Antipanic Bot

Каркас Telegram-бота на `aiogram 3`, Tortoise ORM и Claude API (Anthropic).

## Быстрый старт
1) Создай окружение (пример для Windows PowerShell):
```
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install -r requirements.txt
```
2) Скопируй `env.example` в `.env` и заполни токены:
```
cp env.example .env
```
* `BOT_TOKEN` — Telegram Bot API токен  
* `ANTHROPIC_KEY` — ключ Claude (primary), `OPENAI_KEY` — fallback  
* `ALLOWED_USER_IDS` — пусто = доступ всем; через запятую или JSON-массив для whitelist.

3) Запусти бота:
```
python -m src.main
```

## Что внутри
- `src/main.py` — точка входа, подключает middleware и роутеры, стартует polling.
- `src/bot/handlers` — базовые хендлеры (`/start`, `/help`, `/ping`, `/id`).
- `src/bot/middlewares/access.py` — whitelist на основе `ALLOWED_USER_IDS`.
- `src/database/models.py` — модели пользователей, целей, этапов, шагов и дневников.
- `src/services/ai.py` — обёртка над Claude (Anthropic) с ретраями, fallback на OpenAI.

## Дальнейшие шаги
- Добавить бизнес-хендлеры (онбординг, morning/evening, stuck).
- Подключить миграции через `aerich` (директория `migrations/`).
- Настроить форматирование/линт (black/ruff) и тесты.

