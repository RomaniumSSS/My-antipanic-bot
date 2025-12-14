# Deploy TMA на Railway (вместо Vercel)

## Быстрый деплой через Railway Dashboard

### Шаг 1: Добавить сервис TMA

1. **Railway Dashboard**: https://railway.app
2. Открой свой проект
3. **+ New Service** → **GitHub Repo**
4. Выбери `My-antipanic-bot`
5. Railway создаст новый сервис

---

### Шаг 2: Настроить сервис

**Settings → General:**
- **Service Name**: `tma-frontend`

**Settings → Source:**
- **Root Directory**: `tma-frontend` ⚠️ ОБЯЗАТЕЛЬНО!
- **Branch**: `feature/tma-migration` (или `main`)

**Settings → Build:**
- **Build Command**: `npm install && npm run build` (auto)
- **Start Command**: `npm start` (auto)

**Settings → Networking:**
- Нажми **"Generate Domain"**
- Получишь: `https://tma-frontend-production.up.railway.app`

---

### Шаг 3: Environment Variables

**Variables** (для TMA сервиса):

```bash
# URL твоего бота (FastAPI backend)
NEXT_PUBLIC_API_URL=https://твой-бот.up.railway.app

# Или используй Railway reference:
NEXT_PUBLIC_API_URL=${{bot-service.RAILWAY_PUBLIC_DOMAIN}}
```

**Примечание**: Railway reference автоматически подставит URL бота!

---

### Шаг 4: Deploy

1. Railway автоматически начнёт деплой
2. Смотри логи: **Deployments** → последний деплой
3. Дождись успешного билда (~3-5 мин)

**Проверка успешности**:
```
✓ Building...
✓ Next.js 14.2.35
✓ Compiled successfully
✓ Starting server...
✓ Ready on http://0.0.0.0:3000
```

---

### Шаг 5: Настроить @BotFather

1. Открой https://t.me/BotFather
2. `/mybots` → твой бот
3. **Web App** → **Create Web App**
4. **URL**: `https://tma-frontend-production.up.railway.app` (из Railway)
5. **Short name**: `antipanic`

---

### Шаг 6: Добавить TMA_URL в бот

В сервисе **бота** (не TMA!) добавь переменную:

**Variables** (для bot сервиса):

```bash
# Явно указать URL
TMA_URL=https://tma-frontend-production.up.railway.app

# Или Railway reference (рекомендуется):
TMA_URL=${{tma-frontend.RAILWAY_PUBLIC_DOMAIN}}
```

Railway автоматически перезапустит бот.

---

### Шаг 7: Проверка

1. Открой бота в Telegram
2. `/start`
3. Должна появиться кнопка **"📱 App"**
4. Нажми → TMA откроется
5. Профиль загрузится → микро-действия работают

---

## 🔗 Railway References (автоматическая связь сервисов)

**Преимущество Railway**: сервисы могут ссылаться друг на друга!

### В TMA сервисе:
```bash
NEXT_PUBLIC_API_URL=${{bot-service.RAILWAY_PUBLIC_DOMAIN}}
```

### В Bot сервисе:
```bash
TMA_URL=${{tma-frontend.RAILWAY_PUBLIC_DOMAIN}}
```

Railway автоматически подставит правильные URL!

---

## 🐛 Troubleshooting

### Ошибка: "Root directory not found"

**Решение**:
1. Settings → Source → Root Directory
2. Убедись что указано: `tma-frontend`
3. Redeploy

---

### Ошибка: "Module not found: Can't resolve..."

**Решение**:
1. Проверь что `package.json` в папке `tma-frontend`
2. Build command должен быть: `npm install && npm run build`
3. Очисти кеш: Settings → Clear build cache → Redeploy

---

### TMA показывает "Loading..." вечно

**Причина**: `NEXT_PUBLIC_API_URL` неправильный

**Решение**:
1. TMA Variables → проверь `NEXT_PUBLIC_API_URL`
2. Должен быть URL бота (с https://)
3. Попробуй Railway reference: `${{bot-service.RAILWAY_PUBLIC_DOMAIN}}`
4. Redeploy TMA

---

### Кнопка "📱 App" не появляется

**Причина**: `TMA_URL` не задан в боте

**Решение**:
1. Bot service → Variables
2. Добавь: `TMA_URL=${{tma-frontend.RAILWAY_PUBLIC_DOMAIN}}`
3. Бот автоматически перезапустится
4. Подожди 1-2 мин

---

## 💡 Tips

### 1. Мониторинг логов

**TMA логи**:
```bash
Railway → TMA service → Deployments → View Logs
```

**Bot логи**:
```bash
Railway → Bot service → Deployments → View Logs
```

### 2. Автоматический redeploy

Railway автоматически деплоит при пуше в GitHub:
```bash
git push origin feature/tma-migration
# Railway обнаружит изменения и задеплоит оба сервиса
```

### 3. Custom Domain (опционально)

Можно добавить свой домен:
```bash
Settings → Networking → Custom Domain
→ tma.твойдомен.com
```

---

## 📊 Сравнение: Railway vs Vercel

| Фактор | Railway | Vercel |
|--------|---------|--------|
| **Стоимость** | $5 free/месяц | Бесплатно |
| **Setup** | 1 проект, всё вместе | Отдельный проект |
| **CDN** | Нет (один регион) | Да (глобальный) |
| **Next.js Optimization** | Базовая | Максимальная |
| **Env Vars** | Автосвязь сервисов | Ручная настройка |
| **Скорость билда** | ~3-5 мин | ~2-3 мин |

**Рекомендация**:
- **Railway**: если хочешь всё в одном месте и удобную автосвязь
- **Vercel**: если важна скорость, оптимизация и бесплатность

---

## ✅ Итог

После выполнения всех шагов:

✅ TMA задеплоен на Railway
✅ Получен HTTPS URL от Railway
✅ @BotFather настроен
✅ TMA_URL добавлен в бот
✅ Кнопка "📱 App" работает
✅ Всё в одном Railway проекте

**Stage 4.3 полностью завершён!** 🎉

---

## 🔗 Полезные ссылки

- **Railway Dashboard**: https://railway.app/dashboard
- **Railway Docs**: https://docs.railway.app
- **@BotFather**: https://t.me/BotFather
