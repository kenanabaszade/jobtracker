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


def absolute_url(base: str, href: str | None) -> str | None:
    if not href or href.startswith("#") or href.lower().startswith("javascript:"):
        return None
    href = href.strip()
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("//"):
        parsed = urlparse(base)
        return f"{parsed.scheme}:{href}"
    base_p = urlparse(base)
    if href.startswith("/"):
        return f"{base_p.scheme}://{base_p.netloc}{href}"
    return f"{base_p.scheme}://{base_p.netloc}/{href.lstrip('/')}"


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


async def fetch_html_static(url: str, timeout: float = 30.0, retries: int = 3) -> str:
    headers = {"User-Agent": random_user_agent()}
    last_err: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(retries):
            try:
                await jitter_delay(0.5 + attempt * 0.8, 1.5 + attempt * 0.5)
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as e:
                last_err = e
                logger.warning("GET %s attempt %s/%s: %s", url, attempt + 1, retries, e)
        assert last_err is not None
        raise last_err


async def run_scraper_safe(name: str, coro):
    try:
        return await coro
    except Exception:
        logger.exception("Scraper %s failed", name)
        return []


async def fetch_html_playwright(
    context: BrowserContext,
    url: str,
    *,
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 90_000,
    post_load_delay_ms: int = 0,
    wait_for_selector: str | None = None,
    selector_timeout_ms: int = 45_000,
    scroll_rounds: int = 0,
) -> str:
    page = await context.new_page()
    try:
        await page.set_extra_http_headers({"User-Agent": random_user_agent()})
        await jitter_delay(0.5, 1.5)
        await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
        if wait_for_selector:
            try:
                await page.wait_for_selector(
                    wait_for_selector, timeout=selector_timeout_ms
                )
            except Exception:
                logger.warning(
                    "Timeout waiting for selector %s on %s", wait_for_selector, url
                )
        if post_load_delay_ms > 0:
            await page.wait_for_timeout(post_load_delay_ms)
        else:
            await jitter_delay(0.5, 1.0)
        if scroll_rounds > 0:
            for _ in range(scroll_rounds):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1200)
        return await page.content()
    finally:
        await page.close()
