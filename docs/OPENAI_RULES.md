# OpenAI API (Quick Reference)

> **Note**: Планируется миграция на Claude Sonnet 4.5 (см. BACKLOG.md)

## Async клиент (ОБЯЗАТЕЛЬНО)

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=config.OPENAI_KEY.get_secret_value(),
    timeout=60.0,
)
```

## Базовый запрос

```python
response = await client.chat.completions.create(
    model=config.OPENAI_MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ],
    temperature=0.7,
    max_tokens=500,
)

result = response.choices[0].message.content
```

## Retry с tenacity

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from openai import APIError, RateLimitError, APIConnectionError

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, RateLimitError, APIConnectionError)),
)
async def make_request(messages: list) -> str:
    response = await client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=messages,
    )
    return response.choices[0].message.content or ""
```

## Fallback при ошибках

```python
async def chat_with_fallback(messages: list) -> str:
    try:
        return await make_request(messages)
    except Exception as e:
        logger.error(f"OpenAI request failed: {e}")
        return "Сейчас не получается подключиться к AI. Попробуй позже."
```

## Антипаттерны

```python
# ❌ Синхронный клиент
from openai import OpenAI
client = OpenAI()  # Блокирует event loop!

# ✅ Правильно
from openai import AsyncOpenAI
client = AsyncOpenAI()

# ❌ Хардкод ключа
client = AsyncOpenAI(api_key="sk-...")

# ✅ Правильно
client = AsyncOpenAI(api_key=config.OPENAI_KEY.get_secret_value())
```

## Чеклист

- [ ] `AsyncOpenAI` клиент
- [ ] API ключ из config
- [ ] Retry для transient errors
- [ ] Fallback при ошибках
