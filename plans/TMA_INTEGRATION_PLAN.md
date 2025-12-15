# План интеграции Telegram Mini App (TMA)

## Контекст

- **Текущая ветка**: `clean-backend` — чистый рабочий бэкенд без TMA
- **Бэкенд**: Railway (https://my-antipanic-bot-production.up.railway.app)
- **Фронтенд**: будет на Vercel (отдельный репозиторий)
- **Статус**: бэкенд работает, бот отвечает в Telegram

---

## Фаза 2: Добавление API для TMA

### 2.1 Добавить зависимости

В `requirements.txt` добавить:
```
# FastAPI TMA dependencies
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6
aiohttp-asgi>=0.6.0
aiohttp-cors>=0.7.0
```

### 2.2 Создать структуру API

```
src/
└── interfaces/
    └── api/
        ├── __init__.py
        ├── main.py          # FastAPI app
        ├── auth.py          # Telegram WebApp валидация
        ├── schemas.py       # Pydantic модели
        └── routers/
            ├── __init__.py
            ├── user.py      # GET /api/me
            ├── goal.py      # GET/POST /api/goals
            ├── stats.py     # GET /api/stats
            └── microhit.py  # POST /api/microhit
```

### 2.3 Реализовать endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/me` | GET | Профиль пользователя |
| `/api/goals` | GET | Список целей |
| `/api/goals/{id}` | GET | Детали цели |
| `/api/stats` | GET | Статистика пользователя |
| `/api/microhit` | POST | Генерация микро-действия |

### 2.4 Настроить аутентификацию

- Валидация `initData` из Telegram WebApp
- Проверка подписи через BOT_TOKEN
- Извлечение user_id из initData

### 2.5 Смонтировать FastAPI на aiohttp

В `src/main.py` добавить:
```python
from aiohttp_asgi import ASGIResource
from src.interfaces.api.main import app as fastapi_app

# После создания aiohttp app:
asgi_resource = ASGIResource(fastapi_app)
app.router.add_route("*", "/api{path_info:.*}", asgi_resource)
```

### 2.6 Настроить CORS

```python
import aiohttp_cors

cors_origins = [
    "http://localhost:3000",
    # Vercel домен добавим после деплоя фронтенда
]

cors = aiohttp_cors.setup(app, defaults={...})
```

### 2.7 Деплой и проверка

```bash
git add -A
git commit -m "feat(api): add FastAPI endpoints for TMA"
git push origin clean-backend
```

Проверить:
- `GET /api/me` должен возвращать 401 (нет auth)
- `GET /health` должен работать

---

## Фаза 3: Фронтенд на Vercel

### 3.1 Создать отдельный репозиторий

```bash
# Вариант A: Новый репо из существующего кода
cd ~/
mkdir antipanic-tma-frontend
cp -r ~/My-antipanic-bot/tma-frontend/* antipanic-tma-frontend/
cd antipanic-tma-frontend
git init
git add .
git commit -m "init: TMA frontend for Antipanic Bot"
```

```bash
# Вариант B: Создать с нуля через create-next-app
npx create-next-app@14 antipanic-tma-frontend --typescript --tailwind --app
```

### 3.2 Структура фронтенда

```
antipanic-tma-frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx           # Главная страница
│   └── globals.css
├── lib/
│   ├── api.ts             # API клиент
│   └── telegram.ts        # Telegram WebApp SDK
├── components/
│   ├── UserProfile.tsx
│   ├── GoalCard.tsx
│   └── MicroHitGenerator.tsx
├── .env.example
├── next.config.js
└── package.json
```

### 3.3 Настроить API клиент

```typescript
// lib/api.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function fetchAPI(endpoint: string) {
  const tg = window.Telegram?.WebApp;
  const initData = tg?.initData || "";
  
  const res = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      "Authorization": `tma ${initData}`,
      "Content-Type": "application/json",
    },
  });
  return res.json();
}
```

### 3.4 Залить на GitHub

```bash
gh repo create RomaniumSSS/antipanic-tma-frontend --public
git remote add origin https://github.com/RomaniumSSS/antipanic-tma-frontend.git
git push -u origin main
```

### 3.5 Деплой на Vercel

1. Зайти на https://vercel.com
2. Import Git Repository → выбрать `antipanic-tma-frontend`
3. Environment Variables:
   - `NEXT_PUBLIC_API_URL` = `https://my-antipanic-bot-production.up.railway.app`
4. Deploy

### 3.6 Получить домен

Vercel даст домен типа:
`https://antipanic-tma-frontend.vercel.app`

---

## Фаза 4: Интеграция

### 4.1 Добавить Vercel домен в CORS бэкенда

В `src/main.py` или `src/interfaces/api/main.py`:
```python
cors_origins = [
    "http://localhost:3000",
    "https://antipanic-tma-frontend.vercel.app",  # ← добавить
]
```

### 4.2 Обновить TMA_URL в Railway

В Railway → My-antipanic-bot → Variables:
```
TMA_URL=https://antipanic-tma-frontend.vercel.app
```

### 4.3 Настроить кнопку в боте

В хендлере добавить inline кнопку с WebApp:
```python
from aiogram.types import InlineKeyboardButton, WebAppInfo

button = InlineKeyboardButton(
    text="🚀 Открыть приложение",
    web_app=WebAppInfo(url="https://antipanic-tma-frontend.vercel.app")
)
```

### 4.4 Зарегистрировать Menu Button в BotFather

```
/mybots → @your_bot → Bot Settings → Menu Button
→ Configure menu button
→ URL: https://antipanic-tma-frontend.vercel.app
→ Title: Открыть
```

### 4.5 Тестирование

1. Открыть бота в Telegram
2. Нажать кнопку меню или inline кнопку
3. Убедиться что TMA открывается
4. Проверить что данные загружаются с API

---

## Чеклист готовности

### Бэкенд
- [x] FastAPI endpoints работают (`/api/me`, `/api/goals`, `/api/stats`, `/api/microhit`)
- [x] CORS настроен (localhost:3000 + TMA_URL env var)
- [x] Аутентификация через initData работает (`auth.py`)
- [x] `/api/me` возвращает данные пользователя (auto-creates if not exists)
- [x] FastAPI интегрирован в aiohttp через ASGI adapter

### Фронтенд
- [x] Деплой на Vercel успешен (https://antipanic-tma-frontend.vercel.app)
- [x] GitHub репо: https://github.com/RomaniumSSS/antipanic-tma-frontend
- [x] API запросы проходят
- [x] Telegram WebApp SDK инициализируется
- [x] Данные отображаются

### Интеграция
- [x] TMA_URL добавлен в Railway
- [x] /app команда добавлена в бота
- [x] TMA открывается из Telegram
- [x] Пользователь авторизуется автоматически
- [x] Все endpoints работают в TMA ✅ DONE 2024-12-15

---

## Важные ссылки

- Railway бэкенд: https://my-antipanic-bot-production.up.railway.app
- Telegram WebApp Docs: https://core.telegram.org/bots/webapps
- Vercel Docs: https://vercel.com/docs

---

## Примечания

1. **Раздельные репозитории** — бэкенд и фронтенд в разных репо, чтобы избежать путаницы Railway
2. **Vercel для Next.js** — лучшая поддержка, zero-config деплой
3. **Инкрементальный подход** — сначала минимальный API, потом расширяем
