"""
https://jobs.glorri.az — JS-heavy; job URLs are /vacancies/<org>/<slug> (relative links).
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext

from src.scrapers.base import Job, absolute_url, fetch_html_playwright, run_scraper_safe

logger = logging.getLogger(__name__)

BASE_URL = "https://jobs.glorri.az"
# /vacancies returns 404 for plain GET; the listing is served from the home path.
LISTING_URL = f"{BASE_URL}/"


def _is_glorri_vacancy_url(path: str) -> bool:
    parts = [p for p in path.strip("/").split("/") if p]
    return len(parts) >= 3 and parts[0].lower() == "vacancies"


async def scrape_glorri(context: BrowserContext) -> list[Job]:
    return await run_scraper_safe("glorri", _scrape_glorri(context))


async def _scrape_glorri(context: BrowserContext) -> list[Job]:
    html = await fetch_html_playwright(
        context,
        LISTING_URL,
        wait_until="domcontentloaded",
        post_load_delay_ms=2000,
        wait_for_selector='a[href*="/vacancies/"]',
        selector_timeout_ms=18_000,
        scroll_rounds=6,
    )
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/vacancies/"]'):
        href = link.get("href")
        raw_url = absolute_url(BASE_URL, href)
        if not raw_url or "jobs.glorri.az" not in raw_url:
            continue
        path = urlparse(raw_url).path
        if not _is_glorri_vacancy_url(path):
            continue
        if raw_url in seen:
            continue
        title = (link.get_text() or "").strip()
        title = " ".join(title.split())
        if len(title) < 3:
            h = link.find(["h2", "h3", "h4"])
            if h:
                title = " ".join((h.get_text() or "").split())
        if len(title) < 3:
            continue
        seen.add(raw_url)
        jobs.append(
            Job(
                url=raw_url,
                title=title,
                description=title,
                source_site="glorri",
            )
        )

    logger.info("glorri: %d vacancy links", len(jobs))
    return jobs
