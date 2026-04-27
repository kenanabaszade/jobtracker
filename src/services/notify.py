from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from sqlalchemy import exists, select
from sqlalchemy.orm import selectinload

from src.db.models import Keyword, User, UserJobNotification
from src.db.session import session_scope
from src.scrapers.base import Job, normalize_job_url
from src.services.matching import job_matches_user_keywords
from src.services.source_prefs import user_accepts_source

logger = logging.getLogger(__name__)


async def notify_users_for_jobs(
    bot: Bot,
    session_factory,
    jobs: list[Job],
) -> None:
    if not jobs:
        return

    async with session_scope(session_factory) as session:
        stmt = (
            select(User)
            .options(
                selectinload(User.keywords),
                selectinload(User.source_preferences),
            )
            .where(exists(select(Keyword.id).where(Keyword.user_id == User.id)))
        )
        result = await session.execute(stmt)
        users = list(result.scalars().unique().all())

    for user in users:
        for job in jobs:
            if not user_accepts_source(user, job.source_site):
                continue
            if not job_matches_user_keywords(job, user):
                continue
            norm_url = normalize_job_url(job.url)
            async with session_scope(session_factory) as session:
                existing = await session.execute(
                    select(UserJobNotification.id).where(
                        UserJobNotification.user_id == user.id,
                        UserJobNotification.job_url == norm_url,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                text = (
                    f"New job match ({job.source_site})\n"
                    f"<b>{_escape_html(job.title)}</b>\n"
                    f"{job.url}"
                )
                try:
                    await bot.send_message(
                        user.chat_id,
                        text,
                        parse_mode="HTML",
                        disable_web_page_preview=False,
                    )
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    await bot.send_message(
                        user.chat_id,
                        text,
                        parse_mode="HTML",
                        disable_web_page_preview=False,
                    )
                except Exception:
                    logger.exception(
                        "Failed to notify user_id=%s chat_id=%s",
                        user.telegram_user_id,
                        user.chat_id,
                    )
                    continue

                session.add(
                    UserJobNotification(
                        user_id=user.id,
                        job_url=norm_url,
                        source_site=job.source_site[:128],
                        title_snapshot=job.title[:1024] if job.title else None,
                    )
                )
            await asyncio.sleep(0.05)


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
