"""
https://jobsearch.az — static HTML; use DevTools to refine selectors below.
"""

import logging
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from src.scrapers.base import Job, fetch_html_static, run_scraper_safe

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

BASE_URL = "https://jobsearch.az"


async def scrape_jobsearch_az() -> list[Job]:
    return await run_scraper_safe("jobsearch.az", _scrape_jobsearch_az())


async def _scrape_jobsearch_az() -> list[Job]:
    # TODO: confirm listing URL path and card selectors from live HTML
    listing_url = f"{BASE_URL}/"
    html = await fetch_html_static(listing_url)
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []

    # TODO: replace with real selectors, e.g. soup.select("article.job-listing a")
    for link in soup.select("a[href]"):
        href = link.get("href") or ""
        if not href or href.startswith("#"):
            continue
        title = (link.get_text() or "").strip()
        if len(title) < 3:
            continue
        if "/job" not in href.lower() and "vacancy" not in href.lower():
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
                source_site="jobsearch.az",
            )
        )

    logger.debug("jobsearch.az: parsed %d job links (placeholder logic)", len(jobs))
    return jobs
