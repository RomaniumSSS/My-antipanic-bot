"""
Точка входа Antipanic Bot.
"""

import asyncio
import logging
from typing import Any

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
    storage: RedisStorage | MemoryStorage
    if config.ENVIRONMENT == "production":
        redis = Redis.from_url(
            config.redis_url, decode_responses=True, encoding="utf-8"
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

        app.router.add_get("/health", health)
        app.router.add_get("/cron/tick", cron_tick)

        # === FastAPI TMA Integration ===
        # AICODE-NOTE: Mount FastAPI app for /api/* routes using ASGI adapter
        from src.interfaces.api.main import app as fastapi_app

        async def handle_api(request: web.Request) -> web.Response:
            """
            Proxy /api/* requests to FastAPI ASGI app.
            """
            # Build ASGI scope from aiohttp request
            scope: dict[str, Any] = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": request.method,
                "scheme": request.scheme,
                "path": request.path,
                "query_string": request.query_string.encode(),
                "root_path": "",
                "headers": [
                    (k.lower().encode(), v.encode()) for k, v in request.headers.items()
                ],
                "server": (request.host.split(":")[0], request.url.port or 80),
            }

            # Read request body
            body = await request.read()

            # Capture response
            status_code = 200
            response_headers: list[tuple[bytes, bytes]] = []
            body_parts: list[bytes] = []

            async def receive() -> dict[str, Any]:
                return {"type": "http.request", "body": body, "more_body": False}

            async def send(message: dict[str, Any]) -> None:
                nonlocal status_code, response_headers
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    response_headers = message.get("headers", [])
                elif message["type"] == "http.response.body":
                    body_parts.append(message.get("body", b""))

            # Call FastAPI
            await fastapi_app(scope, receive, send)  # type: ignore[arg-type]

            # Build aiohttp response
            headers = {k.decode(): v.decode() for k, v in response_headers}
            return web.Response(
                status=status_code,
                headers=headers,
                body=b"".join(body_parts),
            )

        # Route all /api/* requests to FastAPI
        app.router.add_route("*", "/api{path_info:.*}", handle_api)
        logger.info("FastAPI TMA endpoints mounted at /api/*")

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
