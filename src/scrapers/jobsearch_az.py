"""
https://jobsearch.az — listing at /vacancies; links use /vacancies/<slug>, not "vacancy".
"""

import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.scrapers.base import Job, absolute_url, fetch_html_static, run_scraper_safe

logger = logging.getLogger(__name__)

BASE_URL = "https://jobsearch.az"
LISTING_URL = f"{BASE_URL}/vacancies"


def _is_vacancy_detail_path(path: str) -> bool:
    parts = [p for p in path.strip("/").split("/") if p]
    return len(parts) >= 2 and parts[0].lower() == "vacancies"


async def scrape_jobsearch_az() -> list[Job]:
    return await run_scraper_safe("jobsearch.az", _scrape_jobsearch_az())


async def _scrape_jobsearch_az() -> list[Job]:
    html = await fetch_html_static(LISTING_URL)
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []
    seen: set[str] = set()

    for link in soup.select('a[href*="/vacancies/"]'):
        href = link.get("href")
        raw_url = absolute_url(BASE_URL, href)
        if not raw_url:
            continue
        path = urlparse(raw_url).path
        if not _is_vacancy_detail_path(path):
            continue
        if raw_url.rstrip("/") == f"{BASE_URL}/vacancies":
            continue
        if raw_url in seen:
            continue
        title = (link.get_text() or "").strip()
        if len(title) < 2:
            h = link.find_parent()
            if h:
                hx = h.find(["h2", "h3", "h4"])
                if hx:
                    title = (hx.get_text() or "").strip()
        if len(title) < 2:
            continue
        seen.add(raw_url)
        jobs.append(
            Job(
                url=raw_url,
                title=title,
                description=title,
                source_site="jobsearch.az",
            )
        )

    logger.info("jobsearch.az: %d vacancy links", len(jobs))
    return jobs
