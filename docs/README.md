# Antipanic Bot Documentation

**Telegram-бот на aiogram 3, Tortoise ORM и Claude API (Anthropic)**

## 📖 Навигация

### 🎓 Guides — Правила разработки
- **[AGENTS.md](guides/AGENTS.md)** — обязательный протокол для AI агентов (читай первым!)
- **[AIOGRAM_RULES.md](guides/AIOGRAM_RULES.md)** — aiogram 3.x patterns (FSM, CallbackData, роутеры)
- **[TORTOISE_RULES.md](guides/TORTOISE_RULES.md)** — Tortoise ORM best practices (prefetch, типизация)
- **[CLAUDE_RULES.md](guides/CLAUDE_RULES.md)** — Claude API (Anthropic) интеграция
- **[MYPY_GUIDE.md](guides/MYPY_GUIDE.md)** — type safety
- **[CRON_SETUP.md](guides/CRON_SETUP.md)** — настройка APScheduler

### 🎯 Product — Продуктовые документы
- **[product.md](product/product.md)** — бизнес-логика, user flows
- **[BACKLOG.md](product/BACKLOG.md)** — roadmap, планы развития (единый источник правды)

### 🔧 Tech — Технические документы
- **[tech.md](tech/tech.md)** — архитектура, data models, стек
- **[RAILWAY_DEPLOY.md](tech/RAILWAY_DEPLOY.md)** — деплой на Railway
- **[TYPE_SAFETY_IMPROVEMENTS.md](tech/TYPE_SAFETY_IMPROVEMENTS.md)** — type safety guide

### 📊 Reports — Отчёты
- **[PROJECT_STRUCTURE_ANALYSIS.md](reports/PROJECT_STRUCTURE_ANALYSIS.md)** — анализ структуры проекта
- **[PROJECT_CLEANUP_REPORT.md](reports/PROJECT_CLEANUP_REPORT.md)** — cleanup analysis
- **[CLEANUP_SUMMARY.md](reports/CLEANUP_SUMMARY.md)** — cleanup summary

### 🤖 Claude Context
- **[CLAUDE.md](claude/CLAUDE.md)** — контекст для Claude Code (claude.ai/code)

### 📋 Plans — Планы развития
- **[active/](plans/active/)** — активные планы (в работе)
- **[archive/](plans/archive/)** — завершённые планы

---

## 🚀 Быстрый старт

1. **Установка зависимостей**:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# или .venv\Scripts\activate на Windows
pip install -r requirements.txt
```

2. **Настройка .env**:
```bash
cp env.example .env
# Заполни: BOT_TOKEN, ANTHROPIC_KEY, OPENAI_KEY (fallback), ALLOWED_USER_IDS
```

3. **Запуск**:
```bash
python -m src.main
```

---

## 🎯 Для AI агентов

**Перед любой работой прочитай**:
1. **[guides/AGENTS.md](guides/AGENTS.md)** — протокол инициализации (ОБЯЗАТЕЛЬНО)
2. Релевантные гайды: AIOGRAM_RULES / TORTOISE_RULES / CLAUDE_RULES

Начинай ответ с: "✅ Verified: [docs read]"

---

## 📁 Структура проекта

```
docs/
├── guides/          # 🎓 Правила разработки
├── product/         # 🎯 Product docs
├── tech/            # 🔧 Technical docs
├── reports/         # 📊 Отчёты
├── claude/          # 🤖 Claude context
└── plans/           # 📋 Планы развития
    ├── active/      # В работе
    └── archive/     # Завершены
```

---

**См. также**: [../README.md](../README.md) в корне проекта

