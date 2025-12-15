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

SYSTEM_PROMPT = """Ты — Antipanic Bot. Твоя задача — заставить пользователя сдвинуться с места.

ПРАВИЛА:
- Никаких "попробуй", "может быть", "если хочешь" — только прямые указания
- "Делаешь это. Прямо сейчас. X минут. Всё."
- Шаги конкретные, измеримые, без воды
- Низкая энергия? Плевать. Даём действие на 2 минуты, но даём
- Тон: жёсткий drill sergeant. Не мотивационная речь, а приказ
- Отвечай на русском языке"""

DECOMPOSE_PROMPT = """Разбей цель на 2-4 этапа. Без воды.

Цель: {goal_text}
Дедлайн: {deadline}
Сегодня: {today}

ТРЕБОВАНИЯ:
- Каждый этап = логический блок. Конкретный
- Равномерно по времени до дедлайна
- Последний этап завершается ДО дедлайна

JSON (БЕЗ markdown, БЕЗ ```):
[
  {{"title": "Конкретное название этапа", "days": число_дней}},
  ...
]"""

STEPS_PROMPT = """Дай 1-3 шага на сегодня. Сейчас.

Этап: {stage_title}
Энергия: {energy}/10
Состояние: {mood}

ПРАВИЛА:
- Энергия 1-3? Один шаг, 5-10 мин. Не ной, делай
- Энергия 4-6? 1-2 шага, 15-30 мин. Никаких отмазок
- Энергия 7-10? 2-3 шага, можно посложнее. Время работать

Формат JSON (БЕЗ markdown, БЕЗ ```):
[
  {{"title": "Конкретное действие без воды", "difficulty": "easy|medium|hard", "minutes": число}},
  ...
]"""

MICROHIT_PROMPT = """Пользователь застрял. Дай микро-удар. Жёстко.

Шаг: {step_title}
Блокер: {blocker_type}
Детали: {details}

Дай ОДНО конкретное действие на 2-5 минут. Прямо сейчас. Максимум 2 предложения.

По типу блокера:
- fear (страшно)? Забей. Делай первые 2 минуты, потом видно будет
- unclear (не знаю с чего)? Вот первый шаг. Делаешь. Думать потом
- no_time (нет времени)? Есть 2 минуты. Хватит лечить. Делаешь
- no_energy (нет сил)? Норм. Действие на минимум. Но делаешь

БЕЗ сочувствия. БЕЗ "попробуй". Только действие."""

MICRO_STEP_PROMPT = """Энергия на нуле ({energy}/10), состояние: "{mood}".
Этап: {stage_title}

Дай ОДНО микро-действие. 2 минуты максимум. Делается прямо сейчас.

Требования:
- Минимум усилий, НО делается
- Нет отговорок "когда будут силы"
- Конкретное действие, не абстракция
- 1-2 предложения. БЕЗ эмодзи. БЕЗ дружелюбности

Низкая энергия — не причина не делать. Причина делать меньше."""

QUIZ_DIAGNOSIS_SYSTEM_PROMPT = """Ты — Antipanic Bot. Скажи пользователю правду: в чём его главный затык и что будет, если не менять.

ПРАВИЛА:
- 3-4 предложения. Прямо. Без сахара
- БЕЗ "судя по тесту", БЕЗ морали
- Главный блокер + последствия, если оставить как есть
- Думай CoT, но пиши только короткий жёсткий диагноз"""

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
    "Твой стопор — высокий тревожный порог. Мозг привык избегать списка дел, "
    "залипать в экран, планировать вместо делания. День → стыд → ещё больше избегания. "
    "Если не прервёшь цикл, он закрепится. Дальше будет хуже: откладываемое копится, "
    "тревога растёт, уверенность в своих силах падает. Выхода не будет."
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
    "Твой стопор — уход в размышления и скролл, когда задача не ясна до шагов. "
    "Пробовал инструменты, бросал — не видел быстрых результатов. Если оставить как есть, "
    "отложенное будет висеть фоном, съедать внимание. Силы уйдут на вину, а не на дела. "
    "Мелочи станут большими проблемами."
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
