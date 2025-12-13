"""
AI Service — обёртка над OpenAI API.
Используется для генерации шагов, анализа состояния, разбивки целей.
"""

import json
import logging
import time
from datetime import date
from typing import Any

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
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

QUIZ_DIAGNOSIS_SYSTEM_PROMPT = """Ты — Antipanic Bot. Твоя задача — кратко описать главную причину прокрастинации пользователя и риск, если не менять паттерн.

Требования:
- 3-4 предложения, дружеский, но прямой тон
- Без морали, без фразы "судя по тесту"
- Укажи главный затык и последствия, если ничего не менять
- Думай по шагам, но показывай только финальный короткий диагноз."""

QUIZ_DIAGNOSIS_FEWSHOT_HIGH_USER = """Уровень зависимости: 78
- Q1 (Недели пролетают): Да
- Q2 (Планирование vs делание): Да
- Q3 (Занятый но ничего не сделал): Да
- Q4 (Тревога растёт): Да
- Q5 (Сколько времени "завтра начну"): Месяц+
- Q6 (Страшно открыть список дел): Да, избегаю
- Q7 (Залипание в экран): Постоянно
- Q8 (Стыдно за день): Да, цикл
- Q9 (Пробовал трекеры): Да, много раз
- Q10 (Есть что откладываешь): Да, и это меня душит"""

QUIZ_DIAGNOSIS_FEWSHOT_HIGH_ASSISTANT = (
    "Тебя держит высокий тревожный порог входа: мозг привык избегать списка дел и "
    "утешать себя планированием/залипанием. Из-за этого каждый день заканчивается "
    "стыдом, а откладываемые задачи копятся и усиливают тревогу. Если оставить так, "
    "замкнутый круг avoidance → тревога → ещё больше avoidance закрепится и заберёт "
    "уверенность, что ты вообще способен двигаться."
)

QUIZ_DIAGNOSIS_FEWSHOT_MID_USER = """Уровень зависимости: 42
- Q1 (Недели пролетают): Скорее да
- Q2 (Планирование vs делание): Скорее да
- Q3 (Занятый но ничего не сделал): Скорее нет
- Q4 (Тревога растёт): Скорее нет
- Q5 (Сколько времени "завтра начну"): Пару недель
- Q6 (Страшно открыть список дел): Иногда
- Q7 (Залипание в экран): Часто
- Q8 (Стыдно за день): Часто
- Q9 (Пробовал трекеры): Пару раз
- Q10 (Есть что откладываешь): Да, несколько"""

QUIZ_DIAGNOSIS_FEWSHOT_MID_ASSISTANT = (
    "Твой стопор — привычка уходить в размышления и экран, когда задача не ясна до "
    "шагов. Ты уже пробовал инструменты, но бросал, потому что не видел быстрых "
    "микро-результатов. Если не поменять паттерн, отложенные мелочи продолжат висеть "
    "фоном и съедать внимание — будешь тратить силы на чувство вины вместо действий."
)


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
    async def _make_request(self, messages: list[dict[str, Any]], **kwargs) -> str:
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

    async def chat(self, messages: list[dict[str, Any]], **kwargs) -> str:
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
    ) -> list[dict[str, Any]]:
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
    ) -> list[dict[str, Any]]:
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

    async def generate_quiz_diagnosis(
        self, answers: list[dict[str, str]], score: float
    ) -> str:
        """Диагноз после квиза зависания."""
        answers_text = "\n".join(
            f"- Q{item.get('number')} ({item.get('question')}): {item.get('answer')}"
            for item in answers
        )
        prompt = f"Уровень зависимости: {score:.0f}\n{answers_text}"
        messages = [
            {"role": "system", "content": QUIZ_DIAGNOSIS_SYSTEM_PROMPT},
            {"role": "user", "content": QUIZ_DIAGNOSIS_FEWSHOT_HIGH_USER},
            {"role": "assistant", "content": QUIZ_DIAGNOSIS_FEWSHOT_HIGH_ASSISTANT},
            {"role": "user", "content": QUIZ_DIAGNOSIS_FEWSHOT_MID_USER},
            {"role": "assistant", "content": QUIZ_DIAGNOSIS_FEWSHOT_MID_ASSISTANT},
            {"role": "user", "content": prompt},
        ]
        response = await self.chat(messages, temperature=0.35, max_tokens=200)
        return response.strip()


# Singleton
ai_service = AIService()
