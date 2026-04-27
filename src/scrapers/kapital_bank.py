"""
Kapital Bank careers run on Bir platform (SPA): https://careers.bir.az/vacancies
hr.kapitalbank.az redirects there; static HTML has almost no rows — Playwright required.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext

from src.scrapers.base import Job, absolute_url, fetch_html_playwright, run_scraper_safe

logger = logging.getLogger(__name__)

BIR_VACANCIES_URL = "https://careers.bir.az/vacancies"
SOURCE_LABEL = "kapital_bank"


async def scrape_kapital_bank(context: BrowserContext) -> list[Job]:
    return await run_scraper_safe("kapital_bank", _scrape_kapital_bank(context))


async def _scrape_kapital_bank(context: BrowserContext) -> list[Job]:
    html = await fetch_html_playwright(
        context,
        BIR_VACANCIES_URL,
        wait_until="domcontentloaded",
        post_load_delay_ms=2500,
        wait_for_selector='a[href*="vacancy"]',
        selector_timeout_ms=20_000,
        scroll_rounds=6,
    )
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []
    seen: set[str] = set()

    for link in soup.select("a[href]"):
        href = link.get("href") or ""
        hlow = href.lower()
        if "vacancy" not in hlow or "filter" in hlow or "login" in hlow:
            continue
        raw_url = absolute_url(BIR_VACANCIES_URL, href)
        if not raw_url or "careers.bir.az" not in raw_url:
            continue
        path = urlparse(raw_url).path.strip("/").split("/")
        if len(path) < 2:
            continue
        if path[0].lower() != "vacancy":
            continue
        if raw_url in seen:
            continue
        title = (link.get_text() or "").strip()
        title = " ".join(title.split())
        if len(title) < 3 or title.lower() in ("vakansiyalar", "bir fürsətdir"):
            continue
        seen.add(raw_url)
        jobs.append(
            Job(
                url=raw_url,
                title=title,
                description=title,
                source_site=SOURCE_LABEL,
            )
        )

    logger.info("kapital_bank (bir.az): %d vacancy links", len(jobs))
    return jobs
