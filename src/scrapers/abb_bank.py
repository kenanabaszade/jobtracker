"""
https://careers.abb-bank.az — vacancy links under /vakansiyalar/v2/<id>
"""

import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.scrapers.base import Job, absolute_url, fetch_html_static, run_scraper_safe

logger = logging.getLogger(__name__)

BASE_URL = "https://careers.abb-bank.az"


async def scrape_abb_bank() -> list[Job]:
    return await run_scraper_safe("abb_bank", _scrape_abb_bank())


async def _scrape_abb_bank() -> list[Job]:
    html = await fetch_html_static(f"{BASE_URL}/")
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="vakansiyalar"]'):
        href = link.get("href")
        raw_url = absolute_url(BASE_URL, href)
        if not raw_url or "abb-bank.az" not in raw_url:
            continue
        path = urlparse(raw_url).path
        if "/vakansiyalar/" not in path.lower():
            continue
        if raw_url in seen:
            continue
        title = (link.get_text() or "").strip()
        if len(title) < 3:
            continue
        seen.add(raw_url)
        jobs.append(
            Job(
                url=raw_url,
                title=title,
                description=title,
                source_site="abb_bank",
            )
        )

    logger.info("abb_bank: %d vacancy links", len(jobs))
    return jobs
