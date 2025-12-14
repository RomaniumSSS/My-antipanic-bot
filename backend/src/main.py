"""
Точка входа Antipanic Bot.
"""

import asyncio
import logging
from urllib.parse import urlparse

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
from src.services import reminders

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

    # Миграция: добавляем новые поля для напоминаний (если их нет)
    try:
        conn = Tortoise.get_connection("default")
        # Проверяем и добавляем колонки если их нет
        await conn.execute_script(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS reminders_enabled BOOLEAN DEFAULT TRUE,
            ADD COLUMN IF NOT EXISTS next_morning_reminder_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS next_evening_reminder_at TIMESTAMPTZ;
        """
        )
        logger.info("Database schema updated (reminders fields)")
    except Exception as e:
        logger.warning(f"Schema migration skipped or failed: {e}")

    # Инициализация reminders service
    reminders.set_bot(bot)
    logger.info("Reminders service initialized")


async def on_shutdown() -> None:
    """Закрытие при остановке."""
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
            config.redis_url, decode_responses=True, encoding="utf-8"
        )
        storage = RedisStorage(redis=redis)

        # Parse Redis URL to log only host:port (without credentials)
        parsed = urlparse(config.redis_url)
        redis_host = parsed.hostname or "unknown"
        redis_port = parsed.port or 6379
        logger.info(f"Using RedisStorage at {redis_host}:{redis_port}")
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

    # Production: webhook mode
    if config.ENVIRONMENT == "production" and config.WEBHOOK_URL:
        from aiohttp import web

        # Set webhook (ensure no double slashes)
        base_url = config.WEBHOOK_URL.rstrip("/")
        webhook_url = f"{base_url}{config.WEBHOOK_PATH}"
        await bot.set_webhook(
            webhook_url,
            drop_pending_updates=True,
        )
        logger.info(f"Webhook set to: {webhook_url}")

        # Create webhook handler
        async def handle_webhook(request: web.Request) -> web.Response:
            """Handle incoming webhook updates."""
            from aiogram.types import Update

            update_data = await request.json()
            update = Update(**update_data)
            await dp.feed_update(bot, update)
            return web.Response()

        # Create aiohttp app
        app = web.Application()
        app.router.add_post(config.WEBHOOK_PATH, handle_webhook)

        # Add root endpoint (for browser access)
        async def root(request: web.Request) -> web.Response:
            return web.json_response(
                {
                    "service": "Antipanic Bot",
                    "status": "running",
                    "mode": "webhook",
                    "docs": "Use Telegram to interact with the bot",
                }
            )

        # Add health check endpoint
        async def health(request: web.Request) -> web.Response:
            return web.json_response({"status": "ok"})

        # Add cron tick endpoint for reminders
        async def cron_tick(request: web.Request) -> web.Response:
            """Process reminders (called by external cron service)."""
            from src.services import reminders

            # Check token
            token = request.query.get("token")
            if not config.CRON_TOKEN or token != config.CRON_TOKEN.get_secret_value():
                return web.json_response({"error": "Unauthorized"}, status=401)

            # Process reminders
            stats = await reminders.process_reminders()
            return web.json_response({"status": "ok", "stats": stats})

        app.router.add_get("/", root)
        app.router.add_get("/health", health)
        app.router.add_get("/cron/tick", cron_tick)

        # Mount FastAPI app for TMA API endpoints
        # FastAPI handles /api/* routes
        from src.interfaces.api.main import app as fastapi_app
        from aiohttp_asgi import ASGIResource

        # Create ASGI resource and mount it for all paths not handled by aiohttp
        asgi_resource = ASGIResource(fastapi_app)
        # Use add_route with path pattern for catch-all
        app.router.add_route("*", "/api{path_info:.*}", asgi_resource)
        logger.info("FastAPI app mounted for /api/* routes")

        # Startup hook for aiohttp
        async def on_app_startup(app: web.Application):
            await _on_startup()

        async def on_app_shutdown(app: web.Application):
            await on_shutdown()

        app.on_startup.append(on_app_startup)
        app.on_shutdown.append(on_app_shutdown)

        # Run aiohttp server
        import os

        port = int(os.getenv("PORT", 8080))
        logger.info(f"Starting webhook server on port {port}")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

        # Keep running
        await asyncio.Event().wait()
    else:
        # Development: polling mode
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
