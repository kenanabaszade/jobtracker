from __future__ import annotations

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import Settings
from src.services.scrape_runner import run_scrape_cycle


def create_scheduler(
    bot: Bot,
    session_factory,
    settings: Settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_scrape_cycle,
        IntervalTrigger(hours=4),
        kwargs={
            "bot": bot,
            "session_factory": session_factory,
            "settings": settings,
        },
        id="job_scrape_cycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
