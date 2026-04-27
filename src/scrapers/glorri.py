"""
https://jobs.glorri.az — likely JavaScript-heavy; use Playwright + BeautifulSoup.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from src.scrapers.base import Job, fetch_html_playwright, run_scraper_safe

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)

BASE_URL = "https://jobs.glorri.az"


async def scrape_glorri(context: BrowserContext) -> list[Job]:
    return await run_scraper_safe("glorri", _scrape_glorri(context))


async def _scrape_glorri(context: BrowserContext) -> list[Job]:
    # TODO: confirm listing path and job card selectors after page load
    listing_url = f"{BASE_URL}/"
    html = await fetch_html_playwright(context, listing_url)
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []

    # TODO: replace with real selectors from rendered DOM
    for link in soup.select("a[href]"):
        href = link.get("href") or ""
        title = (link.get_text() or "").strip()
        if len(title) < 3:
            continue
        if "job" not in href.lower() and "position" not in href.lower():
            continue
        if href.startswith("http"):
            url = href
        else:
            url = f"{BASE_URL.rstrip('/')}/{href.lstrip('/')}"

        jobs.append(
            Job(
                url=url,
                title=title,
                description=title,
                source_site="glorri",
            )
        )

    logger.debug("glorri: parsed %d job links (placeholder logic)", len(jobs))
    return jobs
