"""
AI Service — обёртка над OpenAI API.
Используется для генерации шагов, анализа состояния, разбивки целей.
"""

import json
import logging
import time
from datetime import date
from typing import List, Dict, Any

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from src.config import config

logger = logging.getLogger(__name__)


# === ПРОМПТЫ ===

SYSTEM_PROMPT = """Ты — Antipanic Bot, помощник по достижению целей.
Твоя задача — помогать пользователю двигаться к цели маленькими шагами,
учитывая его текущую энергию и состояние.

Принципы:
- Шаги должны быть конкретными и выполнимыми
- Учитывай уровень энергии при планировании сложности
- При низкой энергии — предлагай более простые действия
- Используй дружелюбный, но не навязчивый тон
- Отвечай на русском языке"""

DECOMPOSE_PROMPT = """Разбей цель на 2-4 последовательных этапа.

Цель: {goal_text}
Дедлайн: {deadline}
Сегодня: {today}

Требования к этапам:
- Каждый этап — логический блок работы
- Этапы должны быть равномерно распределены по времени
- Последний этап должен завершиться до дедлайна

Ответ в формате JSON (без markdown):
[
  {{"title": "Название этапа", "days": число_дней}},
  ...
]"""

STEPS_PROMPT = """Сгенерируй 1-3 конкретных шага на сегодня.

Текущий этап: {stage_title}
Уровень энергии: {energy}/10
Состояние: {mood}

Правила:
- При энергии 1-3: один простой шаг на 5-10 минут
- При энергии 4-6: 1-2 шага на 15-30 минут
- При энергии 7-10: 2-3 шага, можно сложнее

Ответ в формате JSON (без markdown):
[
  {{"title": "Действие", "difficulty": "easy|medium|hard", "minutes": число}},
  ...
]"""

MICROHIT_PROMPT = """Пользователь застрял на шаге. Помоги ему сдвинуться.

Шаг: {step_title}
Причина застревания: {blocker_type}
Детали: {details}

Дай короткий (2-3 предложения) "микро-удар" — минимальное действие,
которое можно сделать прямо сейчас за 2-5 минут, чтобы начать движение.

Учитывай причину:
- fear (страшно): снизь ставки, предложи "разведку"
- unclear (не знаю с чего начать): дай первый микрошаг
- no_time (нет времени): предложи 2-минутную версию
- no_energy (нет сил): предложи пассивный/лёгкий вариант

Ответь текстом без форматирования."""

MICRO_STEP_PROMPT = """Пользователь сообщил о низкой энергии ({energy}/10) и состоянии: "{mood}".
Текущий этап: {stage_title}

Предложи ОДНО супер-микро-действие максимум на 2 минуты, которое:
- Не требует больших усилий
- Психологически снижает порог входа
- Создаёт ощущение движения к цели
- Не вызывает дополнительного сопротивления

Формат ответа — короткое описание действия (1-2 предложения), дружелюбный тон.
Без форматирования, без эмодзи."""


class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.OPENAI_KEY.get_secret_value(), timeout=60.0
        )
        self.model = config.OPENAI_MODEL

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(
            (APIError, APIConnectionError, RateLimitError, ConnectionError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _make_request(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Внутренний метод для запроса к API с ретраями."""
        start_time = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, **kwargs
            )
            latency = time.time() - start_time
            logger.info(f"AI Request OK. Latency: {latency:.2f}s")
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"AI Request failed: {e}")
            raise

    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Основной метод для общения с LLM.
        При ошибке возвращает fallback-сообщение.
        """
        try:
            return await self._make_request(messages, **kwargs)
        except Exception:
            logger.error("All AI retries failed. Returning fallback.")
            return "Сейчас не получается подключиться к AI. Попробуй позже."

    async def decompose_goal(
        self, goal_text: str, deadline: date
    ) -> List[Dict[str, Any]]:
        """
        Разбить цель на 2-4 этапа.

        Returns:
            List[{"title": str, "days": int}]
        """
        prompt = DECOMPOSE_PROMPT.format(
            goal_text=goal_text,
            deadline=deadline.isoformat(),
            today=date.today().isoformat(),
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await self.chat(messages, temperature=0.7)

        try:
            # Пытаемся извлечь JSON из ответа
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1].strip()
                if response.startswith("json"):
                    response = response[4:].strip()
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse decompose response: {response}")
            # Fallback: один этап на всё время
            return [{"title": goal_text, "days": (deadline - date.today()).days}]

    async def generate_steps(
        self, stage_title: str, energy: int, mood: str
    ) -> List[Dict[str, Any]]:
        """
        Сгенерировать шаги на день исходя из этапа и состояния.

        Returns:
            List[{"title": str, "difficulty": str, "minutes": int}]
        """
        prompt = STEPS_PROMPT.format(
            stage_title=stage_title,
            energy=energy,
            mood=mood or "не указано",
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await self.chat(messages, temperature=0.7)

        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1].strip()
                if response.startswith("json"):
                    response = response[4:].strip()
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse steps response: {response}")
            # Fallback: один простой шаг
            return [
                {
                    "title": "Сделать одно маленькое действие по задаче",
                    "difficulty": "easy",
                    "minutes": 10,
                }
            ]

    async def get_microhit(
        self, step_title: str, blocker_type: str, details: str = ""
    ) -> str:
        """
        Получить микро-удар для преодоления застревания.

        Args:
            step_title: Название шага, на котором застрял
            blocker_type: Тип блокера (fear, unclear, no_time, no_energy)
            details: Дополнительные детали от пользователя

        Returns:
            Текст микро-удара
        """
        prompt = MICROHIT_PROMPT.format(
            step_title=step_title,
            blocker_type=blocker_type,
            details=details or "не указаны",
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await self.chat(messages, temperature=0.8, max_tokens=200)
        return response

    async def generate_micro_step(
        self, stage_title: str, energy: int, mood: str
    ) -> str:
        """
        Сгенерировать супер-микро-шаг на 2 минуты для случаев низкой энергии.

        Args:
            stage_title: Название текущего этапа
            energy: Уровень энергии (1-10)
            mood: Описание состояния пользователя

        Returns:
            Текст микро-действия
        """
        prompt = MICRO_STEP_PROMPT.format(
            stage_title=stage_title,
            energy=energy,
            mood=mood or "не указано",
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = await self.chat(messages, temperature=0.8, max_tokens=150)
        return response


# Singleton
ai_service = AIService()
