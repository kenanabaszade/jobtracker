from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from aiogram import Bot
from playwright.async_api import BrowserContext, async_playwright

from src.config import Settings
from src.db.session import get_app_session_factory
from src.scrapers.abb_bank import scrape_abb_bank
from src.scrapers.base import Job, jitter_delay
from src.scrapers.glorri import scrape_glorri
from src.scrapers.jobsearch_az import scrape_jobsearch_az
from src.scrapers.kapital_bank import scrape_kapital_bank
from src.scrapers.linkedin import scrape_linkedin
from src.services.linkedin_keywords import distinct_keywords_for_linkedin
from src.services.notify import notify_users_for_jobs

logger = logging.getLogger(__name__)


_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-sandbox",
]


async def _one_browser_scrape(
    p,
    scrape: Callable[[BrowserContext], Awaitable[list[Job]]],
    label: str,
) -> list[Job]:
    """Fresh Chromium per site so one bad page cannot kill the whole Playwright block."""
    browser = await p.chromium.launch(headless=True, args=_LAUNCH_ARGS)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="az-AZ",
    )
    try:
        return await scrape(context)
    except Exception:
        logger.exception("Playwright session failed: %s", label)
        return []
    finally:
        await context.close()
        await browser.close()


def _merge_jobs_by_url(jobs: list[Job]) -> list[Job]:
    seen: dict[str, Job] = {}
    for job in jobs:
        key = job.normalized_url()
        if key not in seen:
            seen[key] = job
    return list(seen.values())


async def fetch_all_jobs(settings: Settings, session_factory=None) -> list[Job]:
    """Scrape all configured sources and return deduped jobs (no Telegram / DB notify)."""
    logger.info("fetch_all_jobs started")
    jobs: list[Job] = []

    sf = session_factory or get_app_session_factory()

    jobs.extend(await scrape_jobsearch_az())
    await jitter_delay(1.0, 2.5)

    jobs.extend(await scrape_abb_bank())
    await jitter_delay(1.0, 2.5)

    try:
        async with async_playwright() as p:
            # Glorri first (largest feed); Bir.az can crash Chromium on some VPS setups.
            jobs.extend(await _one_browser_scrape(p, scrape_glorri, "glorri"))
            await jitter_delay(1.0, 2.5)
            jobs.extend(await _one_browser_scrape(p, scrape_kapital_bank, "kapital_bank"))
            await jitter_delay(1.0, 2.5)

            kw_list = await distinct_keywords_for_linkedin(
                sf, settings.linkedin_keyword_cycle_limit
            )
            linkedin_urls: list[str] = []
            if kw_list:
                for kw in kw_list:
                    u = settings.resolved_linkedin_search_url(search_keywords=kw)
                    if u:
                        linkedin_urls.append(u)
                logger.info(
                    "linkedin: %d searches from bot keywords (cap %s)",
                    len(linkedin_urls),
                    settings.linkedin_keyword_cycle_limit,
                )
            else:
                u = settings.resolved_linkedin_search_url()
                if u:
                    linkedin_urls.append(u)
                    logger.info("linkedin: 1 search from env URL (no /add keywords in DB)")

            for i, url in enumerate(linkedin_urls):
                jobs.extend(
                    await _one_browser_scrape(
                        p,
                        lambda ctx, linkedin_url=url: scrape_linkedin(ctx, linkedin_url),
                        f"linkedin:{i}",
                    )
                )
                await jitter_delay(0.8, 1.8)
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
    merged = await fetch_all_jobs(settings, session_factory)
    await notify_users_for_jobs(bot, session_factory, merged)
    logger.info("Scrape cycle finished")
