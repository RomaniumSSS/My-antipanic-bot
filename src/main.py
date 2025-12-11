"""
Точка входа Antipanic Bot.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from tortoise import Tortoise

from src.bot.handlers import register_routers
from src.bot.middlewares.access import AccessMiddleware
from src.bot.middlewares.error_handler import ErrorHandlingMiddleware
from src.config import config
from src.database.config import TORTOISE_ORM
from src.services import scheduler

# Настройка логов
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """Инициализация при старте."""
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    logger.info("Database initialized")

    # Инициализация scheduler
    scheduler.set_bot(bot)
    await scheduler.start()
    logger.info("Scheduler started")


async def on_shutdown() -> None:
    """Закрытие при остановке."""
    await scheduler.stop()
    logger.info("Scheduler stopped")

    await Tortoise.close_connections()
    logger.info("Database connections closed")


async def main():
    """Запуск бота."""
    bot = Bot(
        token=config.BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    # FSM Storage: Redis для production, Memory для development
    if config.ENVIRONMENT == "production":
        redis = Redis.from_url(
            config.redis_url,
            decode_responses=True,
            encoding="utf-8"
        )
        storage = RedisStorage(redis=redis)
        logger.info(f"Using RedisStorage at {config.REDIS_HOST}:{config.REDIS_PORT}")
    else:
        storage = MemoryStorage()
        logger.info("Using MemoryStorage (development mode)")

    dp = Dispatcher(storage=storage)

    # Глобальные middleware
    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())

    # Error handling middleware (должен быть последним)
    dp.message.middleware(ErrorHandlingMiddleware())
    dp.callback_query.middleware(ErrorHandlingMiddleware())

    # Подключение роутеров
    register_routers(dp)

    # Startup/shutdown
    async def _on_startup():
        await on_startup(bot)

    dp.startup.register(_on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info(f"Starting Antipanic Bot in {config.ENVIRONMENT} mode...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
