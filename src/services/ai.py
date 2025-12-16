"""
AI Service — обёртка над Claude API (Anthropic).
Используется для генерации шагов, анализа состояния, разбивки целей.

AICODE-NOTE: Мигрировано с OpenAI на Claude Sonnet 4.5 (plan 003).
Поддерживается fallback на OpenAI через config.AI_PROVIDER.
"""

import json
import logging
import time
from datetime import date
from typing import Any

from anthropic import (
    APIConnectionError as AnthropicAPIConnectionError,
)
from anthropic import (
    APIError as AnthropicAPIError,
)
from anthropic import (
    AsyncAnthropic,
)
from anthropic import (
    RateLimitError as AnthropicRateLimitError,
)
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import config

# AICODE-NOTE: Используем TYPE_CHECKING для избежания циклического импорта
# (models -> ai -> models). Реальные типы передаются как параметры в runtime.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.database.models import DailyLog, User

logger = logging.getLogger(__name__)


def get_tone_level(
    user: "User", daily_log: "DailyLog | None"
) -> str:
    """
    Определяет уровень жесткости тона на основе контекста пользователя.

    Логика адаптивного тона (plan 004 — Self-Determination Theory):
    - "maximum": первый шаг дня или после провала streak → нужен пинок
    - "high": обычный день (1-2 шага сделано) → стандартная жесткость
    - "moderate": уже в потоке (3+ шага сегодня) → меньше давления
    - "soft": устойчивая привычка (streak 7+ дней) → поддержка без жесткости

    Args:
        user: User instance (для streak_days)
        daily_log: DailyLog instance или None (для completed_step_ids)

    Returns:
        Уровень тона: "maximum" | "high" | "moderate" | "soft"
    """
    # Fallback на "high" при отсутствии данных
    if user is None:
        return "high"

    # После провала streak или первый день — максимум жесткости
    if user.streak_days == 0:
        return "maximum"

    # Устойчивая привычка (7+ дней подряд) — поддержка без давления
    if user.streak_days >= 7:
        return "soft"

    # Уже в потоке сегодня (3+ шага выполнено) — moderate тон
    if daily_log and len(daily_log.completed_step_ids) >= 3:
        return "moderate"

    # Обычный день — стандартная высокая жесткость
    return "high"


# Инструкции по тону для промптов
TONE_INSTRUCTIONS: dict[str, str] = {
    "maximum": "Максимальная жесткость. Императив без вариантов: 'Делай. Прямо сейчас. Без раздумий.'",
    "high": "Жестко, но с дыханием: 'Делай это. 2 минуты. Начинаешь сейчас.'",
    "moderate": "Нейтрально-прямо: 'Следующий шаг. 5 минут.'",
    "soft": "Поддержка без жесткости: 'Продолжай. Следующий шаг:'",
}


# === ПРОМПТЫ ===

SYSTEM_PROMPT = """Ты drill sergeant для действий, не психолог.

ПРАВИЛА:
- Никакой мотивационной воды ("ты сможешь", "верь в себя") - ЗАПРЕЩЕНО
- Никаких "попробуй", "может быть", "возможно" - ТОЛЬКО императив
- Только команды: "Делай", "Открой", "Напиши", "Ставь таймер"
- Разрешена легкая грубость (не оскорбления!) - "Плевать на настроение, делай"
- Шаги конкретные, измеримые, без абстракций
- Низкая энергия? Норм. Делаешь меньше, но делаешь. Прямо сейчас
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
- Энергия 1-3? Плевать. Делай одно действие на 5 мин. Сейчас
- Энергия 4-6? 1-2 шага, 15-30 мин. Без оправданий
- Энергия 7-10? 2-3 шага, можешь больше. Время действовать

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
- fear (страшно)? Пиши. Хреново — норм. Главное пиши. 5 минут
- unclear (не знаю с чего)? Открой файл. Первый шаг. Делаешь. Без раздумий
- no_time (нет времени)? Есть 2 минуты. Хватит отмазок. Делай
- no_energy (нет сил)? Энергии нет? Норм. Делай меньше, но делай. Прямо сейчас. 2 минуты

БЕЗ сочувствия. БЕЗ "попробуй". БЕЗ "может быть". Только действие."""

MICRO_STEP_PROMPT = """Энергия на нуле ({energy}/10), состояние: "{mood}".
Этап: {stage_title}

Дай ОДНО микро-действие. 2 минуты максимум. Делается прямо сейчас.

Требования:
- Минимум усилий, НО делается
- Нет отговорок "когда будут силы"
- Конкретное действие, не абстракция
- 1-2 предложения. БЕЗ эмодзи. БЕЗ дружелюбности

Энергии нет? Норм. Делай меньше, но делай. Прямо сейчас. 2 минуты."""

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
        """
        Инициализация AI клиента в зависимости от config.AI_PROVIDER.

        Providers:
        - "anthropic" (default): Claude Sonnet 4.5
        - "openai": OpenAI GPT-4 (fallback)

        AICODE-NOTE: Выбор провайдера через .env для быстрого rollback при проблемах.
        """
        self.provider = config.AI_PROVIDER.lower()

        if self.provider == "anthropic":
            if not config.ANTHROPIC_KEY:
                raise ValueError("ANTHROPIC_KEY required for AI_PROVIDER=anthropic")
            self.client = AsyncAnthropic(
                api_key=config.ANTHROPIC_KEY.get_secret_value(),
                timeout=60.0,
            )
            self.model = config.ANTHROPIC_MODEL
        else:
            # Fallback to OpenAI
            if not config.OPENAI_KEY:
                raise ValueError("OPENAI_KEY required for AI_PROVIDER=openai")
            self.client = AsyncOpenAI(
                api_key=config.OPENAI_KEY.get_secret_value(),
                timeout=60.0,
            )
            self.model = config.OPENAI_MODEL
            self.provider = "openai"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(
            (
                APIError,
                APIConnectionError,
                RateLimitError,
                AnthropicAPIError,
                AnthropicAPIConnectionError,
                AnthropicRateLimitError,
                ConnectionError,
            )
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _make_request(self, messages: list[dict[str, Any]], **kwargs) -> str:
        """
        Внутренний метод для запроса к API с ретраями.

        Поддерживает оба провайдера: Claude (Anthropic) и OpenAI.

        AICODE-NOTE: Claude требует max_tokens, OpenAI - нет (опциональный).
        """
        start_time = time.time()
        try:
            if self.provider == "anthropic":
                # Claude API: messages.create() требует max_tokens
                max_tokens = kwargs.pop("max_tokens", 2048)

                # Anthropic использует другой формат messages
                # system prompt передается отдельно
                system_content = ""
                user_messages = []

                for msg in messages:
                    if msg["role"] == "system":
                        system_content = msg["content"]
                    else:
                        user_messages.append(msg)

                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_content,
                    messages=user_messages,
                    **kwargs,
                )
                latency = time.time() - start_time
                logger.info(f"Claude Request OK. Latency: {latency:.2f}s")
                return response.content[0].text
            else:
                # OpenAI API: chat.completions.create()
                response = await self.client.chat.completions.create(
                    model=self.model, messages=messages, **kwargs
                )
                latency = time.time() - start_time
                logger.info(f"OpenAI Request OK. Latency: {latency:.2f}s")
                return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"AI Request failed ({self.provider}): {e}")
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
        self,
        stage_title: str,
        energy: int,
        mood: str,
        user: "User | None" = None,
        daily_log: "DailyLog | None" = None,
    ) -> list[dict[str, Any]]:
        """
        Сгенерировать шаги на день исходя из этапа и состояния.

        Args:
            stage_title: Название текущего этапа
            energy: Уровень энергии (1-10)
            mood: Описание состояния пользователя
            user: User instance для адаптивного тона (опционально)
            daily_log: DailyLog instance для адаптивного тона (опционально)

        Returns:
            List[{"title": str, "difficulty": str, "minutes": int}]
        """
        # Адаптивный тон (plan 004)
        tone_level = get_tone_level(user, daily_log) if user else "high"
        tone_instruction = TONE_INSTRUCTIONS[tone_level]

        system_prompt = f"""{SYSTEM_PROMPT}

Тон этого ответа: {tone_instruction}"""

        prompt = STEPS_PROMPT.format(
            stage_title=stage_title,
            energy=energy,
            mood=mood or "не указано",
        )
        messages = [
            {"role": "system", "content": system_prompt},
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
        self,
        step_title: str,
        blocker_type: str,
        details: str = "",
        user: "User | None" = None,
        daily_log: "DailyLog | None" = None,
    ) -> str:
        """
        Получить микро-удар для преодоления застревания.

        Args:
            step_title: Название шага, на котором застрял
            blocker_type: Тип блокера (fear, unclear, no_time, no_energy)
            details: Дополнительные детали от пользователя
            user: User instance для адаптивного тона (опционально)
            daily_log: DailyLog instance для адаптивного тона (опционально)

        Returns:
            Текст микро-удара

        AICODE-NOTE: Legacy метод для обратной совместимости.
        Для новых use-cases используй get_microhit_variants().
        """
        # Адаптивный тон (plan 004)
        tone_level = get_tone_level(user, daily_log) if user else "high"
        tone_instruction = TONE_INSTRUCTIONS[tone_level]

        system_prompt = f"""{SYSTEM_PROMPT}

Тон этого ответа: {tone_instruction}"""

        prompt = MICROHIT_PROMPT.format(
            step_title=step_title,
            blocker_type=blocker_type,
            details=details or "не указаны",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        response = await self.chat(messages, temperature=0.8, max_tokens=200)
        return response

    async def get_microhit_variants(
        self,
        step_title: str,
        blocker_type: str,
        details: str = "",
        count: int = 3,
        user: "User | None" = None,
        daily_log: "DailyLog | None" = None,
    ) -> list[str]:
        """
        Получить НЕСКОЛЬКО вариантов микро-ударов за один вызов.

        Оптимизация: вместо N параллельных вызовов get_microhit() делаем
        один запрос с просьбой сгенерировать N вариантов в JSON.

        Args:
            step_title: Название шага, на котором застрял
            blocker_type: Тип блокера (fear, unclear, no_time, no_energy)
            details: Дополнительные детали от пользователя
            count: Количество вариантов (по умолчанию 3)
            user: User instance для адаптивного тона (опционально)
            daily_log: DailyLog instance для адаптивного тона (опционально)

        Returns:
            Список текстов микро-ударов (2-3 варианта)

        AICODE-NOTE: Добавлено в plan 003 для оптимизации stuck flow.
        Используется в resolve_stuck_use_case для показа вариантов на выбор.
        """
        # Адаптивный тон (plan 004)
        tone_level = get_tone_level(user, daily_log) if user else "high"
        tone_instruction = TONE_INSTRUCTIONS[tone_level]

        system_prompt = f"""{SYSTEM_PROMPT}

Тон этого ответа: {tone_instruction}"""

        prompt = f"""Пользователь застрял. Дай {count} РАЗНЫХ варианта микро-ударов.

Шаг: {step_title}
Блокер: {blocker_type}
Детали: {details or "не указаны"}

Дай {count} РАЗНЫХ подхода к разблокировке на 2-5 минут каждый:
1. Минимальный вариант (самое простое действие, 1-2 минуты)
2. Умеренный вариант (чуть больше усилий, 3-5 минут)
3. Альтернативный подход (другой угол атаки на задачу)

ВАЖНО:
- Каждый вариант = РАЗНЫЙ подход, не просто разная формулировка
- БЕЗ сочувствия, БЕЗ "попробуй", только команды
- Каждый вариант 1-2 предложения максимум

Формат JSON (БЕЗ markdown, БЕЗ ```):
[
  {{"variant": "minimal", "text": "Конкретное действие 1-2 мин"}},
  {{"variant": "moderate", "text": "Конкретное действие 3-5 мин"}},
  {{"variant": "alternative", "text": "Другой подход к задаче"}}
]"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        response = await self.chat(messages, temperature=0.8, max_tokens=500)

        try:
            # Пытаемся извлечь JSON из ответа
            response_text = response.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1].strip()
                if response_text.startswith("json"):
                    response_text = response_text[4:].strip()

            variants = json.loads(response_text)

            # Извлекаем только текст из вариантов
            if isinstance(variants, list) and len(variants) > 0:
                return [v.get("text", str(v)) for v in variants]

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse microhit variants JSON: {e}. Response: {response}"
            )

        # Fallback: если JSON не распарсился, возвращаем дефолтные варианты
        fallback_variants = [
            f"Открой {step_title.lower()}. Не делай, просто открой. 30 секунд.",
            f"Таймер на 5 минут. Делай {step_title.lower()}. Хреново — норм. Остановишься когда таймер.",
            "Напиши одно предложение по задаче. Плохое — пофиг. Главное напиши. 2 минуты.",
        ]
        return fallback_variants[:count]

    async def generate_micro_step(
        self,
        stage_title: str,
        energy: int,
        mood: str,
        user: "User | None" = None,
        daily_log: "DailyLog | None" = None,
    ) -> str:
        """
        Сгенерировать супер-микро-шаг на 2 минуты для случаев низкой энергии.

        Args:
            stage_title: Название текущего этапа
            energy: Уровень энергии (1-10)
            mood: Описание состояния пользователя
            user: User instance для адаптивного тона (опционально)
            daily_log: DailyLog instance для адаптивного тона (опционально)

        Returns:
            Текст микро-действия
        """
        # Адаптивный тон (plan 004)
        tone_level = get_tone_level(user, daily_log) if user else "high"
        tone_instruction = TONE_INSTRUCTIONS[tone_level]

        system_prompt = f"""{SYSTEM_PROMPT}

Тон этого ответа: {tone_instruction}"""

        prompt = MICRO_STEP_PROMPT.format(
            stage_title=stage_title,
            energy=energy,
            mood=mood or "не указано",
        )
        messages = [
            {"role": "system", "content": system_prompt},
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
