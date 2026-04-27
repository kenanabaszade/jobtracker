from __future__ import annotations

from src.db.models import User
from src.scrapers.base import Job


def job_matches_user_keywords(job: Job, user: User) -> bool:
    if not user.keywords:
        return False
    haystack = f"{job.title}\n{job.description}".lower()
    for kw in user.keywords:
        if kw.text_normalized in haystack:
            return True
    return False
