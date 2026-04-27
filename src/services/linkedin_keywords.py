"""Distinct user keywords to drive LinkedIn search URLs (one scrape per keyword, capped)."""

from __future__ import annotations

from sqlalchemy import func, select

from src.db.models import Keyword, UserSourcePreference
from src.db.session import session_scope


async def distinct_keywords_for_linkedin(session_factory, limit: int) -> list[str]:
    """Keywords from users who have not turned LinkedIn off; one row per normalized keyword."""
    if session_factory is None:
        return []

    async with session_scope(session_factory) as session:
        linkedin_off_users = select(UserSourcePreference.user_id).where(
            UserSourcePreference.source_key == "linkedin",
            UserSourcePreference.enabled.is_(False),
        )
        stmt = (
            select(func.min(Keyword.text_raw))
            .where(~Keyword.user_id.in_(linkedin_off_users))
            .group_by(Keyword.text_normalized)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all() if row[0] and str(row[0]).strip()]
