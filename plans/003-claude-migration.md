# Objective
Полная миграция с OpenAI на Claude Sonnet 4.5, обновление всех промптов на жесткий drill sergeant тон и добавление системы альтернативных вариантов микродействий (2-3 на выбор) для разблокировки ступора.

# Context
- `anthropic>=0.40.0` уже в requirements.txt
- `config.py` уже содержит ANTHROPIC_KEY, ANTHROPIC_MODEL, AI_PROVIDER (кто-то начал миграцию)
- `src/services/ai.py` сейчас использует AsyncOpenAI
- Промпты уже частично жесткие, но нужно усилить drill sergeant стиль
- По BACKLOG.md: замена на Claude = Приоритет 1

# Proposed Steps

## 1. Миграция AIService на Claude (src/services/ai.py)
- [ ] Заменить `from openai import AsyncOpenAI` → `from anthropic import AsyncAnthropic`
- [ ] Заменить `self.client = AsyncOpenAI(...)` → `self.client = AsyncAnthropic(...)`
- [ ] Обновить `_make_request()` под API Claude:
  - OpenAI: `chat.completions.create(model, messages)`
  - Claude: `messages.create(model, max_tokens, messages)` (требует `max_tokens`!)
- [ ] Адаптировать retry exceptions (anthropic.APIError, anthropic.RateLimitError)
- [ ] Использовать `config.AI_PROVIDER` для выбора провайдера (если "anthropic" → Claude, иначе OpenAI)
- [ ] Тесты: проверить что все методы работают (decompose_goal, generate_steps, get_microhit, generate_micro_step)

## 2. Обновление промптов на жесткий drill sergeant тон
Усилить существующие промпты согласно BACKLOG.md § 5.B:

### SYSTEM_PROMPT
- **Было**: "Твоя задача — заставить пользователя сдвинуться с места"
- **Стало**: "Ты drill sergeant для действий, не психолог"
- **Добавить**:
  - Никакой мотивационной воды ("ты сможешь", "верь в себя")
  - Никаких "попробуй", "может быть", "возможно"
  - Только императив: "Делай", "Открой", "Напиши"
  - Разрешено использовать легкую грубость (не оскорбления, а жесткость)

### MICROHIT_PROMPT
- **Усилить**: убрать любые смягчения
- **Примеры** (из BACKLOG.md):
  - ❌ "Попробуй написать пару строк, это поможет преодолеть страх"
  - ✅ "Пиши. Хреново — норм. Главное пиши. 5 минут."

### STEPS_PROMPT
- **Усилить**: более агрессивные формулировки
- **Пример**:
  - ❌ "Энергия 1-3? Один шаг, 5-10 мин. Не ной, делай"
  - ✅ "Энергия 1-3? Плевать. Делай одно действие на 5 мин. Сейчас."

### MICRO_STEP_PROMPT
- **Усилить**: жесткость в конце
- **Было**: "Низкая энергия — не причина не делать. Причина делать меньше."
- **Стало**: "Энергии нет? Норм. Делай меньше, но делай. Прямо сейчас. 2 минуты."

## 3. Альтернативные варианты микродействий (2-3 на выбор)
Реализовать систему выбора вариантов для `get_microhit()`:

### 3.1 Обновить `get_microhit()` в ai.py
- [ ] Создать новый метод `get_microhit_variants()` → возвращает `list[str]` (2-3 варианта)
- [ ] Обновить MICROHIT_PROMPT → просить 3 варианта в JSON:
  ```json
  [
    {"variant": "minimal", "action": "Открой файл. Не пиши, просто открой. 30 секунд."},
    {"variant": "moderate", "action": "Напиши одно предложение. Хреновое — норм. 2 минуты."},
    {"variant": "alternative", "action": "Поставь таймер на 5 минут. Делай хрень. Остановишься когда таймер."}
  ]
  ```
- [ ] Добавить fallback если JSON не парсится → 3 дефолтных варианта
- [ ] Сохранить `get_microhit()` для обратной совместимости (возвращает первый вариант)

### 3.2 Обновить stuck handler (src/bot/handlers/stuck.py)
- [ ] При показе микродействия показывать 3 кнопки (Вариант 1, 2, 3)
- [ ] CallbackData: `MicrohitVariantCallback(microhit_id, variant_index)`
- [ ] После выбора → сохранить в `Step.metadata` для аналитики:
  ```json
  {"chosen_variant": 1, "variants_offered": 3}
  ```

### 3.3 Обновить модель Step (опционально)
- [ ] Добавить поле `variant_chosen: int | None` для аналитики
- [ ] Миграция Aerich

## 4. Обновление документации

### 4.1 Переименовать docs/OPENAI_RULES.md → docs/CLAUDE_RULES.md
- [ ] Обновить все примеры под Anthropic SDK
- [ ] Добавить примеры промптов в drill sergeant стиле
- [ ] Описать систему альтернативных вариантов

### 4.2 Обновить docs/AGENTS.md
- [ ] § 6.3: переименовать "OpenAI API" → "Claude API"
- [ ] Обновить ссылку на CLAUDE_RULES.md

### 4.3 Обновить docs/CLAUDE.md
- [ ] § Critical Architecture Patterns → AI Service Integration:
  - Заменить "AsyncOpenAI" → "AsyncAnthropic"
  - Добавить описание `get_microhit_variants()`

### 4.4 Обновить docs/tech.md
- [ ] § Стек: OpenAI → Claude Sonnet 4.5
- [ ] Добавить примечание о жесткой тональности промптов

### 4.5 Обновить .cursorrules
- [ ] § Anti-Hallucination: переименовать "OpenAI" → "Claude"
- [ ] Добавить правило: "AsyncAnthropic() only, NEVER sync client"

## 5. Обновление .env и примеров
- [ ] Проверить `.env.example` (если есть) → добавить ANTHROPIC_KEY, AI_PROVIDER
- [ ] Обновить README.md → инструкции по получению API ключа Claude

## 6. Тестирование
- [ ] Запустить pytest (все тесты должны проходить)
- [ ] Ручное тестирование:
  - Morning flow → generate_steps()
  - Stuck flow → get_microhit() → выбор из 3 вариантов
  - Onboarding → decompose_goal() (если используется)
- [ ] Проверить тональность: действительно ли пушит к действию?

# Risks

## 1. Breaking changes в API Claude
**Риск**: Anthropic API отличается от OpenAI (требует max_tokens, другая структура messages)
**Митигация**: Добавить fallback на OpenAI через `config.AI_PROVIDER`

## 2. Изменение качества генерации
**Риск**: Claude может генерировать другие формулировки (менее жесткие или слишком жесткие)
**Митигация**: A/B тестирование на себе, настройка temperature/system prompt

## 3. Стоимость API
**Риск**: Claude Sonnet 4.5 может стоить дороже GPT-4
**Митигация**: Мониторинг usage через Anthropic Dashboard, установить rate limits

## 4. Broke промпты после обновления
**Риск**: Жесткий тон может отпугнуть пользователей
**Митигация**: Оставить возможность вернуться к более мягким промптам через feature flag

## 5. Альтернативные варианты усложняют UX
**Риск**: 3 кнопки вместо 1 = больше выбора = паралич решения
**Митигация**: Пометить один вариант как "Рекомендуемый" (первый), остальные "Альтернатива"

# Rollback

## Быстрый откат (если Claude не работает)
1. В `.env` изменить `AI_PROVIDER=openai`
2. Проверить что OPENAI_KEY заполнен
3. Перезапустить бота
→ Бот переключится обратно на OpenAI без изменения кода

## Полный откат (если нужно вернуть старые промпты)
1. Git revert коммита с миграцией
2. Восстановить `docs/OPENAI_RULES.md`
3. Удалить `docs/CLAUDE_RULES.md`
4. Перезапустить бота

## Откат альтернативных вариантов
1. Удалить CallbackData для вариантов из stuck.py
2. Вернуть старый `get_microhit()` без вариантов
3. Убрать кнопки выбора в UI

---

**Оценка времени**: 2-3 часа (миграция AIService + промпты + тестирование)
**Приоритет**: Высокий (Приоритет 1 из BACKLOG.md)

