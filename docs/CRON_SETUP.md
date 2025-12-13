# Настройка Cron для напоминаний

## Обзор

Бот использует простую архитектуру напоминаний без APScheduler:
- Храним `next_morning_reminder_at` и `next_evening_reminder_at` в БД (UTC)
- Внешний cron вызывает `/cron/tick?token=SECRET` каждые 5-10 минут
- Бот выбирает пользователей с просроченными напоминаниями и отправляет сообщения
- После отправки пересчитывается следующее время напоминания

## Railway Setup (рекомендуется)

Railway не имеет встроенного cron, используйте внешний сервис:

### Вариант 1: cron-job.org (бесплатно)

1. Зайди на https://cron-job.org
2. Зарегистрируйся
3. Create new cronjob:
   - Title: `Antipanic Bot Reminders`
   - URL: `https://your-app.railway.app/cron/tick?token=YOUR_CRON_TOKEN`
   - Schedule: `*/5 * * * *` (каждые 5 минут)
   - Save

### Вариант 2: Railway Cron Plugin (если появится)

Railway может добавить cron plugin в будущем.

### Вариант 3: GitHub Actions (бесплатно)

Создай `.github/workflows/cron.yml`:

```yaml
name: Cron Tick

on:
  schedule:
    # Каждые 5 минут
    - cron: '*/5 * * * *'
  workflow_dispatch: # Для ручного запуска

jobs:
  tick:
    runs-on: ubuntu-latest
    steps:
      - name: Call cron endpoint
        run: |
          curl -f "https://your-app.railway.app/cron/tick?token=${{ secrets.CRON_TOKEN }}"
```

Добавь `CRON_TOKEN` в GitHub Secrets:
1. Repository → Settings → Secrets → Actions
2. New repository secret: `CRON_TOKEN` = твой токен

## Генерация CRON_TOKEN

```bash
# Генерируй случайную строку
openssl rand -hex 32
```

Добавь в Railway Variables:
```
CRON_TOKEN=сгенерированный_токен
```

## Проверка работы

### 1. Health check
```bash
curl https://your-app.railway.app/health
# Должно вернуть: {"status": "ok"}
```

### 2. Cron tick (с токеном)
```bash
curl "https://your-app.railway.app/cron/tick?token=YOUR_TOKEN"
# Должно вернуть: {"status": "ok", "stats": {"morning_sent": 0, "evening_sent": 0}}
```

### 3. Проверка без токена (должна вернуть 401)
```bash
curl https://your-app.railway.app/cron/tick
# Должно вернуть: {"error": "Unauthorized"}
```

## Логи

В Railway смотри логи после вызова `/cron/tick`:
```
Reminders processed: 2 morning, 3 evening
Morning reminder sent to user 12345
Evening reminder sent to user 67890
```

## Математика дат

### Как работает расчёт:

1. **Пользователь завершает онбординг:**
   - `reminder_morning = "09:00"` (локальное время пользователя)
   - `timezone_offset = 3` (UTC+3 для Москвы)
   - Рассчитываем `next_morning_reminder_at` в UTC

2. **Расчёт следующего напоминания:**
   ```python
   user_local_now = utc_now + timedelta(hours=timezone_offset)
   local_reminder_dt = combine(date, time(9, 0))

   if local_reminder_dt <= user_local_now:
       local_reminder_dt += timedelta(days=1)

   utc_reminder_dt = local_reminder_dt - timedelta(hours=timezone_offset)
   ```

3. **Cron tick (каждые 5 минут):**
   ```python
   users = User.filter(
       reminders_enabled=True,
       next_morning_reminder_at__lte=now_utc
   )

   for user in users:
       send_morning_reminder(user)
       user.next_morning_reminder_at = calculate_next(...)
       user.save()
   ```

### Пример:

- Пользователь в UTC+3 (Москва)
- Хочет напоминание в 09:00 по Москве
- Сейчас: 2025-12-13 20:00 UTC (23:00 МСК)

Расчёт:
1. 09:00 МСК сегодня = 06:00 UTC
2. 06:00 UTC < 20:00 UTC (прошло) → берём завтра
3. `next_morning_reminder_at = 2025-12-14 06:00 UTC`

Когда будет 2025-12-14 06:00 UTC:
- Cron tick найдёт этого пользователя
- Отправит напоминание
- Пересчитает на 2025-12-15 06:00 UTC

## Часовые пояса

Пользователи могут указать свой часовой пояс:
- `timezone_offset = 0` → UTC (Лондон)
- `timezone_offset = 3` → UTC+3 (Москва)
- `timezone_offset = -5` → UTC-5 (Нью-Йорк)

Все расчёты в UTC, отображение в локальном времени пользователя.

## Преимущества этого подхода

✅ Нет APScheduler → нет greenlet → нет libstdc++.so.6 проблем
✅ Простая архитектура — только даты и математика
✅ Легко дебажить — всё в БД
✅ Персистентность из коробки
✅ Работает с любым cron-сервисом
✅ Можно вызвать `/cron/tick` вручную для теста

## Troubleshooting

### Напоминания не приходят

1. Проверь что cron работает (логи cron-job.org)
2. Проверь `/cron/tick` возвращает stats > 0
3. Проверь `reminders_enabled = True` в User
4. Проверь `next_*_reminder_at` установлены в User (не NULL)

### Дубликаты напоминаний

- Cron не должен вызываться чаще чем раз в 1 минуту
- После отправки напоминания `next_*_reminder_at` обновляется на следующий день

### Неправильное время

- Проверь `timezone_offset` в User
- Проверь что `reminder_morning` / `reminder_evening` в локальном времени пользователя
