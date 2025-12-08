"""
AI Service — обёртка над OpenAI API.
Используется для генерации шагов, анализа состояния, разбивки целей.
"""

import logging
import time
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


class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.OPENAI_KEY.get_secret_value(),
            timeout=60.0
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
                model=self.model,
                messages=messages,
                **kwargs
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


# Singleton
ai_service = AIService()
