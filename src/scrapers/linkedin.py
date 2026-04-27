"""
LinkedIn job search — best-effort; set LINKEDIN_JOB_SEARCH_URL in .env.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext

from src.scrapers.base import Job, absolute_url, fetch_html_playwright, run_scraper_safe

logger = logging.getLogger(__name__)

_LINKEDIN_HOST = "linkedin.com"


def _normalize_linkedin_job_url(href: str) -> str | None:
    if "linkedin.com" not in href:
        return None
    parsed = urlparse(href)
    if _LINKEDIN_HOST not in (parsed.netloc or "").lower():
        return None
    path = parsed.path or ""
    if "/jobs/view/" not in path and "/jobs/collections/" not in path:
        if not re.search(r"/jobs/\d+", path):
            return None
    clean = urlunparse(
        (parsed.scheme or "https", parsed.netloc.lower(), path, "", "", "")
    )
    if clean.endswith("/"):
        clean = clean[:-1]
    return clean


async def scrape_linkedin(context: BrowserContext, search_url: str | None) -> list[Job]:
    return await run_scraper_safe("linkedin", _scrape_linkedin(context, search_url))


async def _scrape_linkedin(context: BrowserContext, search_url: str | None) -> list[Job]:
    if not search_url:
        logger.info("linkedin: LINKEDIN_JOB_SEARCH_URL not set, skipping")
        return []

    html = await fetch_html_playwright(
        context,
        search_url,
        wait_until="domcontentloaded",
        timeout_ms=120_000,
        post_load_delay_ms=5000,
    )
    soup = BeautifulSoup(html, "lxml")
    jobs: list[Job] = []
    seen: set[str] = set()

    for link in soup.select("a[href]"):
        href = link.get("href") or ""
        full = absolute_url("https://www.linkedin.com/", href)
        if not full:
            continue
        norm = _normalize_linkedin_job_url(full)
        if not norm or norm in seen:
            continue
        title = " ".join((link.get_text() or "").split())
        if len(title) < 2 or title.lower() in ("apply", "see more", "show more"):
            continue
        seen.add(norm)
        jobs.append(
            Job(
                url=norm,
                title=title,
                description=title,
                source_site="linkedin",
            )
        )

    logger.info("linkedin: %d job links (best-effort)", len(jobs))
    return jobs
