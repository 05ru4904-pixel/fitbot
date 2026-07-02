import asyncio
import logging
import os

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonCommands, MenuButtonWebApp, WebAppInfo

from api.main import app as webapp
from config import settings
from db.database import init_db
from handlers import correction, diary, photo, profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    logger.info("Database initialized.")

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(photo.router)
    dp.include_router(correction.router)
    dp.include_router(profile.router)
    dp.include_router(diary.router)

    # Remove the slash-command list; actions live on the reply keyboard instead.
    await bot.delete_my_commands()

    # Turn the chat menu button (≡, left of the input) into an "Open diary" Mini App launcher.
    if settings.webapp_url and not settings.webapp_url.startswith("https://example"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Открыть дневник",
                web_app=WebAppInfo(url=settings.webapp_url),
            )
        )
    else:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    # Run the Mini App web server on the same service (Railway maps $PORT to the public domain)
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config(webapp, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    logger.info("Bot + Mini App starting on port %s...", port)
    try:
        await asyncio.gather(
            dp.start_polling(bot),
            server.serve(),
        )
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
