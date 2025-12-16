# Claude API (Anthropic) - Quick Reference

> **Note**: Мигрировано с OpenAI на Claude Sonnet 4.5 (plan 003-claude-migration.md)
> Fallback на OpenAI через `AI_PROVIDER=openai` в .env

## Async клиент (ОБЯЗАТЕЛЬНО)

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(
    api_key=config.ANTHROPIC_KEY.get_secret_value(),
    timeout=60.0,
)
```

## Базовый запрос

```python
response = await client.messages.create(
    model=config.ANTHROPIC_MODEL,  # claude-sonnet-4-20250514
    max_tokens=2048,  # ОБЯЗАТЕЛЬНЫЙ параметр для Claude!
    system="Ты drill sergeant для действий, не психолог.",
    messages=[
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": "Понял."},
        {"role": "user", "content": "Дай шаги на сегодня"},
    ],
    temperature=0.6,
)

result = response.content[0].text
```

## Ключевые отличия от OpenAI

| OpenAI | Claude (Anthropic) |
|--------|-------------------|
| `chat.completions.create()` | `messages.create()` |
| `max_tokens` опциональный | `max_tokens` **ОБЯЗАТЕЛЬНЫЙ** |
| System в messages | System как отдельный параметр |
| `response.choices[0].message.content` | `response.content[0].text` |

## Retry с tenacity

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from anthropic import (
    APIError as AnthropicAPIError,
    RateLimitError as AnthropicRateLimitError,
    APIConnectionError as AnthropicAPIConnectionError,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        AnthropicAPIError,
        AnthropicRateLimitError,
        AnthropicAPIConnectionError,
    )),
)
async def make_request(messages: list) -> str:
    response = await client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text
```

## Fallback при ошибках

```python
async def chat_with_fallback(messages: list) -> str:
    try:
        return await make_request(messages)
    except Exception as e:
        logger.error(f"Claude request failed: {e}")
        return "Сейчас не получается подключиться к AI. Попробуй позже."
```

## Drill Sergeant Tone (Критично!)

**ВАЖНО**: Тональность зависит от контекста взаимодействия:

### 1. ВО ВРЕМЯ ДЕЙСТВИЯ → Жесткий императив
Когда генерируем шаги, микро-удары, пушим к действию — drill sergeant на максимум.

**SYSTEM_PROMPT для генерации действий:**
```
Ты drill sergeant для действий, не психолог.

ПРАВИЛА:
- Никакой мотивационной воды ("ты сможешь", "верь в себя") - ЗАПРЕЩЕНО
- Никаких "попробуй", "может быть", "возможно" - ТОЛЬКО императив
- Только команды: "Делай", "Открой", "Напиши"
- Разрешена легкая грубость (не оскорбления!) - "Плевать на настроение, делай"
```

**Примеры drill sergeant формулировок (ДО/ВО ВРЕМЯ действия):**
- ❌ "Попробуй написать пару строк, это поможет преодолеть страх"
- ✅ "Пиши. Хреново — норм. Главное пиши. 5 минут."

- ❌ "Может быть, стоит начать с простого шага"
- ✅ "Открой файл. Первый шаг. Делаешь. Без раздумий."

- ❌ "Если у тебя нет энергии, попробуй что-то полегче"
- ✅ "Энергии нет? Норм. Делай меньше, но делай. Прямо сейчас. 2 минуты."

### 2. ПОСЛЕ ЗАВЕРШЕНИЯ → Похвала + буст вперед
Когда пользователь закрыл действие (completed step) — позитивное подкрепление, но БЕЗ перехваливания.

**Тональность после completion:**
- Признание факта ("Сделал — зачёт")
- Фиксация прогресса ("+20 XP", "streak 5 дней")
- Буст на следующее действие ("Двигай дальше", "Идёшь к цели")
- БЕЗ: "Ты молодец!", "Я горжусь тобой", "Ты супер!" (слишком мягко)

**Примеры похвалы (ПОСЛЕ действия):**
- ✅ "Сделал. +20 XP. Следующий шаг?"
- ✅ "Готово. Двигаешься к цели. Streak 3 дня — продолжай."
- ✅ "Закрыл шаг. Зачёт. Что дальше по плану?"
- ❌ "Ты большой молодец! Я так горжусь тобой!" (перехваливание)
- ❌ "Отлично, попробуй теперь что-нибудь ещё" (мягко + "попробуй")

**Баланс тональности:**
```
Генерация шагов/микро-ударов → ЖЕСТКИЙ императив (100%)
                    ↓
         Пользователь делает
                    ↓
    Завершение действия → Похвала + буст (энергия идти дальше)
                    ↓
Генерация следующих шагов → снова ЖЕСТКИЙ императив
```

### 3. Применение в коде

**Для генерации действий** (используют жесткий тон):
- `generate_steps()` — ИМПЕРАТИВ
- `get_microhit()` / `get_microhit_variants()` — ИМПЕРАТИВ
- `generate_micro_step()` — ИМПЕРАТИВ

**Для completion feedback** (нужна похвала):
- В handlers после `step.status = "completed"` → ответ бота должен быть позитивным
- Показ XP/streak → с буст-тоном ("Двигай дальше", "Идёшь к цели")
- НЕ генерировать через AI (фиксированные шаблоны быстрее и дешевле)

**Пример в handler:**
```python
# После completion шага
await message.answer(
    f"Сделал. +{step.xp_reward} XP. Двигаешься к цели.\n"
    f"Streak: {user.streak_days} дней. Продолжай."
)
```

## Альтернативные варианты микродействий

Система выбора из 2-3 вариантов (plan 003):

```python
# Новый метод (оптимизированный)
variants = await ai_service.get_microhit_variants(
    step_title="Написать введение",
    blocker_type="fear",
    details="страшно что получится плохо",
    count=3,
)
# Returns: ["Вариант 1...", "Вариант 2...", "Вариант 3..."]

# Legacy метод (для обратной совместимости)
single = await ai_service.get_microhit(
    step_title="Написать введение",
    blocker_type="fear",
    details="страшно что получится плохо",
)
# Returns: "Вариант 1..."
```

## Антипаттерны

```python
# ❌ Синхронный клиент
from anthropic import Anthropic
client = Anthropic()  # Блокирует event loop!

# ✅ Правильно
from anthropic import AsyncAnthropic
client = AsyncAnthropic()

# ❌ Хардкод ключа
client = AsyncAnthropic(api_key="sk-ant-...")

# ✅ Правильно
client = AsyncAnthropic(api_key=config.ANTHROPIC_KEY.get_secret_value())

# ❌ Забыли max_tokens (обязательный параметр)
response = await client.messages.create(
    model=model,
    messages=messages,
)

# ✅ Правильно
response = await client.messages.create(
    model=model,
    max_tokens=2048,
    messages=messages,
)

# ❌ System prompt в messages (как в OpenAI)
messages = [
    {"role": "system", "content": "You are..."},
    {"role": "user", "content": "Hello"},
]

# ✅ Правильно (system отдельно)
response = await client.messages.create(
    system="You are...",
    messages=[
        {"role": "user", "content": "Hello"},
    ],
)
```

## Чеклист

- [ ] `AsyncAnthropic` клиент (NEVER sync!)
- [ ] API ключ из config
- [ ] `max_tokens` обязательно указан
- [ ] System prompt через параметр `system`, не в messages
- [ ] Retry для transient errors
- [ ] Fallback при ошибках
- [ ] Drill sergeant тон в промптах (без "попробуй", "может быть")

## Rollback на OpenAI

Если Claude не работает или слишком дорогой:

1. В `.env` изменить:
   ```
   AI_PROVIDER=openai
   OPENAI_KEY=sk-...
   ```

2. Перезапустить бота → автоматически переключится на OpenAI

3. Код совместим с обоими провайдерами через `AIService._make_request()`

