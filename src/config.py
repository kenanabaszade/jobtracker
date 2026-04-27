from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./data/jobtracker.db"
    linkedin_job_search_url: str | None = None
    # Added to the LinkedIn search URL query (set empty in .env to disable location filter).
    linkedin_location: str | None = Field(default="Baku, Azerbaijan")
    # Optional LinkedIn geoId (pick from browser URL when you filter by city). Empty = omit.
    linkedin_geo_id: str | None = None
    # Max distinct /add keywords (per cycle) used as LinkedIn search queries (users with LinkedIn on).
    linkedin_keyword_cycle_limit: int = Field(default=12, ge=1, le=40)
    log_level: str = "INFO"
    # Scrape cadence: 240 = every 4 hours. Use 1–5 for testing; set back for production.
    scrape_interval_minutes: int = Field(default=240, ge=1)
    # If true, run one scrape right after startup (then continue on the interval).
    scrape_on_startup: bool = False

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url
        if url.startswith("sqlite+aiosqlite:///./"):
            rel = url.removeprefix("sqlite+aiosqlite:///./")
            abs_path = (_PROJECT_ROOT / rel).resolve()
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{abs_path.as_posix()}"
        return url

    def resolved_linkedin_search_url(self, search_keywords: str | None = None) -> str | None:
        """Build LinkedIn job search URL with optional keywords, location, geoId."""
        base = (self.linkedin_job_search_url or "").strip()
        sk = (search_keywords or "").strip()
        if not base:
            if not sk:
                return None
            base = "https://www.linkedin.com/jobs/search/"
        parts = urlsplit(base)
        q = dict(parse_qsl(parts.query, keep_blank_values=True))
        if sk:
            q["keywords"] = sk
        loc = (self.linkedin_location or "").strip()
        if loc:
            q["location"] = loc
        gid = (self.linkedin_geo_id or "").strip()
        if gid:
            q["geoId"] = gid
        new_query = urlencode(list(q.items()))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def get_settings() -> Settings:
    return Settings()
