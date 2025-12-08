# Правила работы с OpenAI API

Паттерны и best practices для интеграции с OpenAI в Antipanic Bot.

---

## 1. Инициализация клиента

### Async клиент (ОБЯЗАТЕЛЬНО для aiogram)

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=config.OPENAI_KEY.get_secret_value(),
    timeout=60.0,
)
```

### Настройка через pydantic-settings

```python
# src/config.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENAI_KEY: SecretStr
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TIMEOUT: float = 60.0
    OPENAI_MAX_TOKENS: int = 1000
```

---

## 2. Chat Completions

### Базовый запрос

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

### Структура сообщений

```python
messages = [
    # Системное сообщение — роль, контекст, ограничения
    {
        "role": "system",
        "content": """Ты — помощник в Telegram-боте Antipanic.
Твоя задача — помогать пользователям преодолевать прокрастинацию.
Отвечай кратко, по делу, максимум 2-3 предложения.
Если не знаешь ответа — скажи об этом."""
    },
    # История диалога (опционально)
    {"role": "user", "content": "Предыдущий вопрос"},
    {"role": "assistant", "content": "Предыдущий ответ"},
    # Текущий запрос
    {"role": "user", "content": "Текущий вопрос"},
]
```

---

## 3. Streaming (для длинных ответов)

### Async streaming

```python
async with client.chat.completions.stream(
    model=config.OPENAI_MODEL,
    messages=messages,
) as stream:
    full_response = ""
    async for event in stream:
        if event.type == "content.delta":
            chunk = event.delta.content or ""
            full_response += chunk
            # Можно отправлять чанки пользователю
    
    return full_response
```

### Получение финального результата

```python
async with client.chat.completions.stream(...) as stream:
    async for _ in stream:
        pass  # обрабатываем события

completion = await stream.get_final_completion()
result = completion.choices[0].message.content
```

---

## 4. Параметры генерации

### Рекомендуемые значения для бота

```python
# Для генерации шагов/советов
GENERATION_PARAMS = {
    "temperature": 0.7,      # Баланс креативности
    "max_tokens": 500,       # Лимит ответа
    "top_p": 0.9,            # Nucleus sampling
}

# Для анализа/классификации
ANALYSIS_PARAMS = {
    "temperature": 0.3,      # Более детерминированно
    "max_tokens": 200,
}

# Для микро-ударов (короткие советы)
MICROHIT_PARAMS = {
    "temperature": 0.5,
    "max_tokens": 150,
}
```

---

## 5. Промпты для Antipanic Bot

### Системный промпт (базовый)

```python
SYSTEM_PROMPT = """Ты — Antipanic Bot, помощник для преодоления прокрастинации.

ПРАВИЛА:
1. Отвечай КРАТКО — максимум 2-3 предложения
2. Предлагай КОНКРЕТНЫЕ действия, не абстракции
3. Шаги должны быть выполнимы за 5-30 минут
4. Используй эмодзи для структуры (🟢 лёгкий, 🟡 средний, 🔴 сложный)
5. Если не хватает информации — спроси, не додумывай

ФОРМАТ ШАГОВ:
🟢 [5-10 мин] Название шага
🟡 [15-30 мин] Название шага
🔴 [45-60 мин] Название шага
"""
```

### Промпт для декомпозиции цели

```python
DECOMPOSE_PROMPT = """Разбей цель на 2-3 этапа.

ЦЕЛЬ: {goal}
ДЕДЛАЙН: {deadline}

Формат ответа:
1. [Название этапа] — краткое описание (срок: X дней)
2. [Название этапа] — краткое описание (срок: X дней)
...

Этапы должны быть последовательными и конкретными."""
```

### Промпт для генерации шагов

```python
STEPS_PROMPT = """Предложи 1-3 шага на сегодня.

КОНТЕКСТ:
- Цель: {goal}
- Текущий этап: {stage}
- Энергия пользователя: {energy}/10
- Состояние: {mood}

ПРАВИЛА:
- При энергии 1-3: только 🟢 лёгкие шаги (5-10 мин)
- При энергии 4-6: 🟢 и 🟡 шаги
- При энергии 7-10: можно 🔴 сложные шаги

Ответь списком шагов."""
```

### Промпт для микро-удара

```python
MICROHIT_PROMPT = """Пользователь застрял. Дай микро-удар на 2-5 минут.

БЛОКЕР: {blocker_type}
ДЕТАЛИ: {details}
ТЕКУЩИЙ ШАГ: {current_step}

Предложи ОДНО конкретное микро-действие, которое можно сделать прямо сейчас.
Формат: короткое действие + почему это поможет (1 предложение)."""
```

---

## 6. Обработка ошибок и retry

### Retry с tenacity

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

### Fallback при ошибках

```python
async def chat_with_fallback(messages: list) -> str:
    try:
        return await make_request(messages)
    except Exception as e:
        logger.error(f"OpenAI request failed: {e}")
        return "Сейчас не получается подключиться к AI. Попробуй позже."
```

---

## 7. Структура AI сервиса

```python
# src/services/ai.py
import logging
from typing import List, Dict, Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import config

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.OPENAI_KEY.get_secret_value(),
            timeout=config.OPENAI_TIMEOUT,
        )
        self.model = config.OPENAI_MODEL

    async def _request(
        self,
        messages: List[Dict[str, Any]],
        **kwargs
    ) -> str:
        """Базовый запрос к API."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content or ""

    async def decompose_goal(self, goal: str, deadline: str) -> str:
        """Декомпозиция цели на этапы."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": DECOMPOSE_PROMPT.format(
                goal=goal,
                deadline=deadline
            )},
        ]
        return await self._request(messages, temperature=0.5, max_tokens=500)

    async def generate_steps(
        self,
        goal: str,
        stage: str,
        energy: int,
        mood: str
    ) -> str:
        """Генерация шагов на день."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": STEPS_PROMPT.format(
                goal=goal,
                stage=stage,
                energy=energy,
                mood=mood
            )},
        ]
        return await self._request(messages, temperature=0.7, max_tokens=400)

    async def get_microhit(
        self,
        blocker_type: str,
        details: str,
        current_step: str
    ) -> str:
        """Микро-удар при застревании."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": MICROHIT_PROMPT.format(
                blocker_type=blocker_type,
                details=details,
                current_step=current_step
            )},
        ]
        return await self._request(messages, temperature=0.6, max_tokens=150)


# Singleton
ai_service = AIService()
```

---

## 8. Логирование и метрики

```python
import time
import logging

logger = logging.getLogger(__name__)

async def _request_with_logging(self, messages, **kwargs) -> str:
    start = time.time()
    try:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        latency = time.time() - start
        
        # Логируем метрики (без PII!)
        logger.info(
            "OpenAI request",
            extra={
                "latency_ms": int(latency * 1000),
                "model": self.model,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        )
        
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"OpenAI error: {type(e).__name__}: {e}")
        raise
```

---

## 9. Антипаттерны

### ❌ Синхронный клиент

```python
# ПЛОХО — блокирует event loop
from openai import OpenAI
client = OpenAI()

# ХОРОШО
from openai import AsyncOpenAI
client = AsyncOpenAI()
```

### ❌ Хардкод API ключа

```python
# ПЛОХО
client = AsyncOpenAI(api_key="sk-...")

# ХОРОШО
client = AsyncOpenAI(api_key=config.OPENAI_KEY.get_secret_value())
```

### ❌ Слишком длинные промпты

```python
# ПЛОХО — промпт на 2000 токенов с лишней информацией

# ХОРОШО — краткий, структурированный промпт
```

### ❌ Отсутствие обработки ошибок

```python
# ПЛОХО
result = await client.chat.completions.create(...)

# ХОРОШО
try:
    result = await client.chat.completions.create(...)
except RateLimitError:
    # retry или fallback
except APIError as e:
    logger.error(f"API error: {e}")
    return FALLBACK_MESSAGE
```

---

## 10. Чеклист

- [ ] Используется `AsyncOpenAI` клиент
- [ ] API ключ из `config`, не хардкод
- [ ] Есть retry логика для transient errors
- [ ] Есть fallback сообщение при ошибках
- [ ] Промпты вынесены в константы
- [ ] Логируется latency и usage (без PII)
- [ ] temperature/max_tokens настроены под задачу

