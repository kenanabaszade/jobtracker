"""
https://careers.abb-bank.az — adjust listing URL and selectors to match live site.
"""

import logging

from bs4 import BeautifulSoup

from src.scrapers.base import Job, fetch_html_static, run_scraper_safe

logger = logging.getLogger(__name__)

BASE_URL = "https://careers.abb-bank.az"


async def scrape_abb_bank() -> list[Job]:
    return await run_scraper_safe("abb_bank", _scrape_abb_bank())


async def _scrape_abb_bank() -> list[Job]:
    # TODO: set correct careers listing URL
    listing_url = f"{BASE_URL}/"
    html = await fetch_html_static(listing_url)
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []

    # TODO: replace with role/vacancy card selectors
    for link in soup.select("a[href]"):
        href = link.get("href") or ""
        title = (link.get_text() or "").strip()
        if len(title) < 3:
            continue
        if not any(x in href.lower() for x in ("job", "vacancy", "career", "position")):
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
                source_site="abb_bank",
            )
        )

    logger.debug("abb_bank: parsed %d job links (placeholder logic)", len(jobs))
    return jobs
