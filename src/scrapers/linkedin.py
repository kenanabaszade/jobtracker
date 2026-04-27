"""
LinkedIn job search URLs — best-effort; pages often require login or block automation.
Set LINKEDIN_JOB_SEARCH_URL in .env. Official APIs are preferred for production.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from src.scrapers.base import Job, fetch_html_playwright, run_scraper_safe

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)


async def scrape_linkedin(context: BrowserContext, search_url: str | None) -> list[Job]:
    return await run_scraper_safe("linkedin", _scrape_linkedin(context, search_url))


async def _scrape_linkedin(context: BrowserContext, search_url: str | None) -> list[Job]:
    if not search_url:
        logger.info("linkedin: LINKEDIN_JOB_SEARCH_URL not set, skipping")
        return []

    html = await fetch_html_playwright(context, search_url)
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []

    # TODO: replace with stable selectors from LinkedIn job search results (changes frequently)
    for link in soup.select("a[href*='jobs/view'], a[href*='/jobs/']"):
        href = link.get("href") or ""
        title = (link.get_text() or "").strip()
        if len(title) < 2:
            continue
        if href.startswith("http"):
            url = href.split("?")[0] if "linkedin.com" in href else href
        else:
            url = f"https://www.linkedin.com{href}" if href.startswith("/") else href

        jobs.append(
            Job(
                url=url,
                title=title,
                description=title,
                source_site="linkedin",
            )
        )

    logger.debug("linkedin: parsed %d job links (placeholder logic)", len(jobs))
    return jobs
