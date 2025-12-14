# 🚀 Быстрый деплой TMA — Шпаргалка

## ⚡ За 5 минут

### 1️⃣ Vercel (веб-интерфейс)

https://vercel.com → Login → Add New → Project

**Настройки:**
- Repository: `My-antipanic-bot`
- Root Directory: `tma-frontend` ⚠️
- Framework: Next.js (auto)
- Environment Variables:
  ```
  NEXT_PUBLIC_API_URL = https://ваш-бот.railway.app
  ```

→ **Deploy** → Получить URL → **Сохрани!**

---

### 2️⃣ @BotFather

https://t.me/BotFather

```
/mybots
→ Выбрать бота
→ Web App → Create Web App
→ URL: https://ваш-app.vercel.app
→ Short name: antipanic
```

---

### 3️⃣ Railway

https://railway.app → Ваш проект → Bot service → Variables

```
TMA_URL = https://ваш-app.vercel.app
```

→ **Add** → Бот автоматически перезапустится

---

### 4️⃣ Проверка

Telegram → Ваш бот → `/start`

✅ Должна появиться кнопка **"📱 App"**
✅ Нажать → TMA открывается
✅ Профиль загружается

---

## 🔧 Если что-то не работает

| Проблема | Решение |
|----------|---------|
| Нет кнопки "📱 App" | Railway → Variables → проверь `TMA_URL` → Redeploy |
| TMA не открывается | @BotFather → проверь Web App URL правильный |
| "Loading..." вечно | Vercel → проверь `NEXT_PUBLIC_API_URL` правильный |
| Ошибка "Unauthorized" | Открывай TMA ТОЛЬКО через Telegram (не в браузере) |

---

## 📝 URL-ы для копирования

**Railway Bot URL** (для Vercel env var):
```
Railway Dashboard → Bot Service → Settings → Domains → Public URL
```

**Vercel TMA URL** (для Railway и @BotFather):
```
Vercel → Deployments → Latest → Visit → Копировать URL
```

---

**Полная инструкция**: См. `VERCEL_DEPLOY_GUIDE.md`
