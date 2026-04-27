"""Per-user toggles for which job sources appear in notifications and /jobs."""

from __future__ import annotations

from src.db.models import User

KNOWN_SOURCES: tuple[str, ...] = (
    "jobsearch.az",
    "abb_bank",
    "kapital_bank",
    "glorri",
    "linkedin",
)

KNOWN_SOURCES_SET = frozenset(KNOWN_SOURCES)

# Short names accepted in /source <name> on|off
SOURCE_ALIASES: dict[str, str] = {
    "jobsearch": "jobsearch.az",
    "jobsearch_az": "jobsearch.az",
    "abb": "abb_bank",
    "abb_bank": "abb_bank",
    "kapital": "kapital_bank",
    "kapital_bank": "kapital_bank",
    "bir": "kapital_bank",
    "glorri": "glorri",
    "linkedin": "linkedin",
}


def normalize_source_key(raw: str) -> str | None:
    s = raw.strip().lower()
    if s in SOURCE_ALIASES:
        return SOURCE_ALIASES[s]
    if s in KNOWN_SOURCES_SET:
        return s
    return None


def user_accepts_source(user: User, source_site: str) -> bool:
    prefs = getattr(user, "source_preferences", None) or []
    for p in prefs:
        if p.source_key == source_site:
            return p.enabled
    return True
