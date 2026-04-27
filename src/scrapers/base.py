from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx
from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)

USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


async def jitter_delay(min_s: float = 0.5, max_s: float = 2.5) -> None:
    import asyncio

    await asyncio.sleep(random.uniform(min_s, max_s))


@dataclass
class Job:
    url: str
    title: str
    description: str
    source_site: str
    external_id: str | None = None

    def normalized_url(self) -> str:
        return normalize_job_url(self.url)


def normalize_job_url(url: str) -> str:
    parsed = urlparse(url.strip())
    fragment = ""
    query_parts = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            if pair.lower().startswith("utm_"):
                continue
            query_parts.append(pair)
    query = "&".join(query_parts)
    return urlunparse(
        (parsed.scheme, parsed.netloc.lower(), parsed.path, parsed.params, query, fragment)
    )


async def fetch_html_static(url: str, timeout: float = 30.0) -> str:
    headers = {"User-Agent": random_user_agent()}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        await jitter_delay(0.3, 1.2)
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


async def run_scraper_safe(name: str, coro):
    try:
        return await coro
    except Exception:
        logger.exception("Scraper %s failed", name)
        return []


async def fetch_html_playwright(context: BrowserContext, url: str) -> str:
    page = await context.new_page()
    try:
        await page.set_extra_http_headers({"User-Agent": random_user_agent()})
        await jitter_delay(0.5, 1.5)
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await jitter_delay(0.5, 1.0)
        return await page.content()
    finally:
        await page.close()
