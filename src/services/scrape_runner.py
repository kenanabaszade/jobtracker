from __future__ import annotations

import logging

from aiogram import Bot
from playwright.async_api import async_playwright

from src.config import Settings
from src.scrapers.abb_bank import scrape_abb_bank
from src.scrapers.base import Job, jitter_delay
from src.scrapers.glorri import scrape_glorri
from src.scrapers.jobsearch_az import scrape_jobsearch_az
from src.scrapers.kapital_bank import scrape_kapital_bank
from src.scrapers.linkedin import scrape_linkedin
from src.services.notify import notify_users_for_jobs

logger = logging.getLogger(__name__)


def _merge_jobs_by_url(jobs: list[Job]) -> list[Job]:
    seen: dict[str, Job] = {}
    for job in jobs:
        key = job.normalized_url()
        if key not in seen:
            seen[key] = job
    return list(seen.values())


async def fetch_all_jobs(settings: Settings) -> list[Job]:
    """Scrape all configured sources and return deduped jobs (no Telegram / DB notify)."""
    logger.info("fetch_all_jobs started")
    jobs: list[Job] = []

    jobs.extend(await scrape_jobsearch_az())
    await jitter_delay(1.0, 2.5)

    jobs.extend(await scrape_abb_bank())
    await jitter_delay(1.0, 2.5)

    jobs.extend(await scrape_kapital_bank())
    await jitter_delay(1.0, 2.5)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            try:
                jobs.extend(await scrape_glorri(context))
                await jitter_delay(1.0, 2.5)
                jobs.extend(
                    await scrape_linkedin(context, settings.linkedin_job_search_url)
                )
            finally:
                await context.close()
                await browser.close()
    except Exception:
        logger.exception("Playwright scrape block failed")

    merged = _merge_jobs_by_url(jobs)
    logger.info("fetch_all_jobs collected %d unique jobs", len(merged))
    return merged


async def run_scrape_cycle(
    bot: Bot,
    session_factory,
    settings: Settings,
) -> None:
    logger.info("Scrape cycle started")
    merged = await fetch_all_jobs(settings)
    await notify_users_for_jobs(bot, session_factory, merged)
    logger.info("Scrape cycle finished")
