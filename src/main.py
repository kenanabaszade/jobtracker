from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from src.bot.middlewares import DbSessionMiddleware
from src.bot.router import main_router
from src.config import get_settings
from src.db.session import (
    create_async_db_engine,
    get_session_factory,
    init_db,
    set_app_session_factory,
)
from src.services.scrape_runner import run_scrape_cycle
from src.services.scheduler import create_scheduler


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    engine = create_async_db_engine(settings)
    await init_db(engine)
    session_factory = get_session_factory(engine)
    set_app_session_factory(session_factory)

    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware(session_factory))
    dp.include_router(main_router)

    scheduler = create_scheduler(bot, session_factory, settings)
    scheduler.start()
    if settings.scrape_on_startup:
        asyncio.create_task(
            run_scrape_cycle(bot, session_factory, settings)
        )

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
