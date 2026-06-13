"""Entry point — run Telegram bot polling + FastAPI dashboard concurrently."""

import asyncio
import logging

import uvicorn
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from .config import TELEGRAM_BOT_TOKEN, LOG_LEVEL, API_PORT
from .handlers import (
    start_handler,
    help_handler,
    status_handler,
    menu_handler,
    adguard_handler,
    mode_handler,
    speed_handler,
    preferences_handler,
    callback_handler,
    error_handler,
)
from .api import app as fastapi_app

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)


# ── Application ──────────────────────────────────────────────────────────────

async def main() -> None:
    """Build and run Telegram bot + FastAPI server concurrently."""
    # Build Telegram application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("menu", menu_handler))
    application.add_handler(CommandHandler("adguard", adguard_handler))
    application.add_handler(CommandHandler("mode", mode_handler))
    application.add_handler(CommandHandler("speed", speed_handler))
    application.add_handler(CommandHandler("preferences", preferences_handler))

    # Inline-keyboard callback handler (catch-all)
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Global error handler
    application.add_error_handler(error_handler)

    # Configure FastAPI/uvicorn server
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)

    logger.info("🤖 Starting Telegram bot + Dashboard API on port %d…", API_PORT)

    # Run both concurrently
    async with application:
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)

        try:
            # Run FastAPI server (blocks until shutdown)
            await server.serve()
        finally:
            # Cleanup Telegram on shutdown
            await application.updater.stop()
            await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
