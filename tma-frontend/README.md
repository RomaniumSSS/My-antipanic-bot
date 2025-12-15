# Antipanic TMA Frontend

Telegram Mini App frontend для Antipanic Bot.

## Технологии

- **Next.js 14** — React framework с App Router
- **TypeScript** — типизация
- **Tailwind CSS** — стилизация
- **Telegram WebApp SDK** — интеграция с Telegram

## Разработка

```bash
# Установить зависимости
npm install

# Запустить dev сервер
npm run dev

# Открыть http://localhost:3000
```

## Структура

```
app/
├── layout.tsx      # Корневой layout с TelegramProvider
├── page.tsx        # Главная страница (статистика + цели)
├── providers.tsx   # React контексты (Telegram)
└── globals.css     # Глобальные стили + Tailwind

lib/
├── telegram.ts     # Telegram WebApp SDK типы и хелперы
└── api.ts          # API клиент для бэкенда

components/
├── StatsCard.tsx   # Карточка статистики пользователя
├── GoalCard.tsx    # Карточка цели
└── UserProfile.tsx # Профиль пользователя
```

## Переменные окружения

```bash
# .env.local
NEXT_PUBLIC_API_URL=https://my-antipanic-bot-production.up.railway.app
NEXT_PUBLIC_DEBUG=true
```

## Деплой на Vercel

1. Создать репозиторий на GitHub
2. Импортировать в Vercel
3. Настроить Environment Variables:
   - `NEXT_PUBLIC_API_URL` = URL бэкенда на Railway
4. Deploy

## API Endpoints

Фронтенд использует следующие endpoints бэкенда:

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/me` | GET | Профиль пользователя |
| `/api/stats` | GET | Статистика |
| `/api/goals` | GET | Список целей |
| `/api/goals/{id}` | GET | Детали цели |
| `/api/microhit` | POST | Генерация микро-шага |

Аутентификация через заголовок `Authorization: tma {initData}`.
