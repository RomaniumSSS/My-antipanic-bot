# FastAPI Testing Guide

## Быстрый старт

### 1. Запустить FastAPI сервер

```bash
python run_api.py
```

Сервер запустится на http://localhost:8000

### 2. Открыть документацию

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 3. Проверить health endpoint

```bash
curl http://localhost:8000/health
```

Ответ: `{"status":"healthy"}`

## Тестирование эндпоинтов

### Базовые эндпоинты (без auth)

```bash
# Health check
curl http://localhost:8000/health

# Root
curl http://localhost:8000/

# OpenAPI schema
curl http://localhost:8000/openapi.json
```

### Dev эндпоинты (требуют telegram_id)

**Сначала получите список пользователей:**

```bash
curl http://localhost:8000/dev/users
```

**Используйте telegram_id из ответа для тестирования:**

```bash
# Замените 123456 на ваш telegram_id
TELEGRAM_ID=123456

# Профиль пользователя
curl "http://localhost:8000/dev/me?telegram_id=$TELEGRAM_ID"

# Активная цель
curl "http://localhost:8000/dev/goals?telegram_id=$TELEGRAM_ID"

# Статистика
curl "http://localhost:8000/dev/stats?telegram_id=$TELEGRAM_ID"

# История выполненных шагов
curl "http://localhost:8000/dev/history?telegram_id=$TELEGRAM_ID"

# Генерация микро-ударов
curl -X POST "http://localhost:8000/dev/microhit/generate?telegram_id=$TELEGRAM_ID&step_title=Начать%20работу&blocker_type=fear"

# Выполнение микро-удара (замените STEP_ID)
curl -X POST "http://localhost:8000/dev/microhit/complete?telegram_id=$TELEGRAM_ID&step_id=STEP_ID"
```

## Автоматические тесты

### Запуск всех тестов

```bash
pytest tests/test_api.py -v
```

### Запуск конкретных тестов

```bash
# Только базовые тесты (без БД)
pytest tests/test_api.py::test_health_endpoint -v
pytest tests/test_api.py::test_root_endpoint -v
pytest tests/test_api.py::test_openapi_schema -v

# Тесты с БД (требуют пользователя в БД)
pytest tests/test_api.py::test_dev_get_me -v
pytest tests/test_api.py::test_dev_get_stats -v
```

### Результаты тестов

✅ **Рабочие тесты** (4/11):
- `test_health_endpoint` - health check
- `test_root_endpoint` - root endpoint
- `test_api_me_without_auth` - проверка auth
- `test_openapi_schema` - OpenAPI схема

⚠️ **Тесты требующие БД** (7/11):
- Требуют пользователя в базе данных
- Создайте пользователя через бота: `/start`

## Примеры использования

### 1. Получить профиль пользователя

```bash
curl "http://localhost:8000/dev/me?telegram_id=123456"
```

Ответ:
```json
{
  "telegram_id": 123456,
  "username": "user",
  "first_name": "John",
  "xp": 150,
  "level": 2,
  "streak_days": 5,
  "timezone_offset": 0
}
```

### 2. Получить активную цель

```bash
curl "http://localhost:8000/dev/goals?telegram_id=123456"
```

Ответ:
```json
{
  "id": 1,
  "title": "Выучить Python",
  "current_stage": "Начало",
  "progress": 30,
  "deadline": "2025-12-31"
}
```

### 3. Сгенерировать микро-удары

```bash
curl -X POST "http://localhost:8000/dev/microhit/generate?telegram_id=123456&step_title=Написать%20код&blocker_type=fear"
```

Ответ:
```json
{
  "options": [
    {"index": 0, "text": "Открой редактор. Прямо сейчас. 30 секунд."},
    {"index": 1, "text": "Создай пустой файл main.py. 1 минута."},
    {"index": 2, "text": "Напиши print('Hello'). Запусти. 2 минуты."}
  ],
  "step_id": 42
}
```

### 4. Выполнить микро-удар

```bash
curl -X POST "http://localhost:8000/dev/microhit/complete?telegram_id=123456&step_id=42"
```

Ответ:
```json
{
  "xp_earned": 10,
  "total_xp": 160,
  "streak_days": 5,
  "level": 2
}
```

## Troubleshooting

### Ошибка: "User not found"

**Решение**: Создайте пользователя через бота

```bash
# 1. Запустите бота
python -m src.main

# 2. В Telegram отправьте /start боту

# 3. Получите telegram_id
curl http://localhost:8000/dev/users
```

### Ошибка: "No active goal"

**Решение**: Создайте цель через бота

```bash
# В Telegram:
# 1. /start
# 2. Следуйте инструкциям для создания первой цели
```

### Ошибка: "Connection refused"

**Решение**: Убедитесь что FastAPI сервер запущен

```bash
python run_api.py
```

## Полезные команды

```bash
# Запустить сервер с автоперезагрузкой
python run_api.py

# Запустить только тесты без БД
pytest tests/test_api.py -k "not dev" -v

# Запустить тесты с подробным выводом
pytest tests/test_api.py -vv

# Посмотреть coverage
pytest tests/test_api.py --cov=src/interfaces/api
```

## Следующие шаги

После успешного тестирования API:

1. ✅ FastAPI работает
2. ✅ Dev эндпоинты доступны
3. ✅ Pytest тесты проходят

**Дальше**:
- Создать Next.js фронт (Этап 4.2)
- Подключить TMA к боту (Этап 4.3)
