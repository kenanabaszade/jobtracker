import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from src.config import get_settings
from src.db.models import Keyword, User, UserJobNotification, UserSourcePreference
from src.scrapers.base import Job
from src.services.matching import job_matches_user_keywords
from src.services.source_prefs import (
    KNOWN_SOURCES,
    normalize_source_key,
    user_accepts_source,
)
from src.db.session import get_app_session_factory
from src.services.scrape_runner import fetch_all_jobs

logger = logging.getLogger(__name__)

_MAX_JOBS_IN_REPLY = 60
_CHUNK_SOFT_LIMIT = 3800

router = Router(name="commands")

HELP_TEXT = (
    "<b>Job Tracker — commands</b>\n\n"
    "<b>/start</b> — Register and see a short command list.\n"
    "<b>/help</b> — This help (all commands explained).\n\n"
    "<b>/add</b> <code>keyword</code> — Track a word or phrase. Matching is "
    "case-insensitive in job title and description. Also used for LinkedIn "
    "search queries (with your location from the server config).\n"
    "<b>/list</b> — Show your tracked keywords.\n"
    "<b>/remove</b> <code>keyword</code> — Stop tracking one keyword.\n\n"
    "<b>/jobs</b> — Run a live scrape and list <i>current</i> matches for your "
    "keywords (respects /source toggles). Can take about a minute.\n\n"
    "<b>/sources</b> — Show each job site (ON/OFF) for your account.\n"
    "<b>/source</b> <code>site</code> <code>on|off</code> — Turn a source on or off "
    "for alerts and /jobs. Sites: <code>jobsearch</code>, <code>abb</code>, "
    "<code>kapital</code>, <code>glorri</code>, <code>linkedin</code>.\n"
    "Examples: <code>/source linkedin off</code> · <code>/source off kapital</code>\n\n"
    "<b>/clear</b> — Reset <i>your bot data</i>: all keywords, site toggles, and "
    "“already notified” history so you can get fresh alerts. "
    "<b>Telegram does not let bots delete the chat screen</b>; old messages stay "
    "in the app until you delete them yourself.\n\n"
    "Tip: use /help any time."
)


def _normalize_keyword(text: str) -> str:
    return text.strip().lower()


@router.message(Command("start"))
async def cmd_start(message: Message, db_session) -> None:
    uid = message.from_user.id if message.from_user else message.chat.id
    chat_id = message.chat.id

    result = await db_session.execute(
        select(User).where(User.telegram_user_id == uid)
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_user_id=uid, chat_id=chat_id)
        db_session.add(user)
    else:
        user.chat_id = chat_id

    await db_session.flush()
    await message.answer(
        "Welcome to the Job Tracker bot.\n\n"
        "Quick commands: /help (full guide), /add, /list, /remove, /jobs, "
        "/sources, /source, /clear"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.message(Command("add"), F.text)
async def cmd_add(message: Message, command: CommandObject, db_session) -> None:
    raw = (command.args or "").strip()
    if not raw:
        await message.answer("Usage: /add <keyword>\nExample: /add ios")
        return

    uid = message.from_user.id if message.from_user else message.chat.id
    result = await db_session.execute(
        select(User).where(User.telegram_user_id == uid)
    )
    user = result.scalar_one_or_none()
    if user is None:
        await message.answer("Please use /start first.")
        return

    norm = _normalize_keyword(raw)
    existing = await db_session.execute(
        select(Keyword).where(
            Keyword.user_id == user.id,
            Keyword.text_normalized == norm,
        )
    )
    if existing.scalar_one_or_none() is not None:
        await message.answer(f"You are already tracking “{raw}”.")
        return

    db_session.add(Keyword(user_id=user.id, text_raw=raw, text_normalized=norm))
    await message.answer(f"Added keyword: {raw}")


@router.message(Command("list"))
async def cmd_list(message: Message, db_session) -> None:
    uid = message.from_user.id if message.from_user else message.chat.id
    result = await db_session.execute(
        select(User)
        .options(selectinload(User.keywords))
        .where(User.telegram_user_id == uid)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.keywords:
        await message.answer("You have no keywords yet. Use /add <keyword>.")
        return

    lines = sorted(k.text_raw for k in user.keywords)
    await message.answer("Your keywords:\n" + "\n".join(f"• {line}" for line in lines))


@router.message(Command("remove"), F.text)
async def cmd_remove(message: Message, command: CommandObject, db_session) -> None:
    raw = (command.args or "").strip()
    if not raw:
        await message.answer("Usage: /remove <keyword>")
        return

    uid = message.from_user.id if message.from_user else message.chat.id
    norm = _normalize_keyword(raw)

    result = await db_session.execute(
        select(User).where(User.telegram_user_id == uid)
    )
    user = result.scalar_one_or_none()
    if user is None:
        await message.answer("Please use /start first.")
        return

    del_result = await db_session.execute(
        delete(Keyword).where(
            Keyword.user_id == user.id,
            Keyword.text_normalized == norm,
        )
    )
    if del_result.rowcount == 0:
        await message.answer(f"No keyword matching “{raw}”.")
        return

    await message.answer(f"Removed keyword: {raw}")


def _job_list_chunks(matched: list[Job], total_scraped: int) -> list[str]:
    header = (
        f"Current job matches ({len(matched)} shown, {total_scraped} scraped total):\n\n"
    )
    chunks: list[str] = []
    buf = header
    for job in matched:
        line = f"• [{job.source_site}] {job.title}\n{job.url}\n\n"
        if len(line) > 3500:
            line = line[:3490] + "…\n\n"
        if len(buf) + len(line) > _CHUNK_SOFT_LIMIT:
            chunks.append(buf.rstrip())
            buf = line
        else:
            buf += line
    if buf.strip():
        chunks.append(buf.rstrip())
    return chunks


@router.message(Command("jobs"))
async def cmd_jobs(message: Message, db_session) -> None:
    uid = message.from_user.id if message.from_user else message.chat.id
    result = await db_session.execute(
        select(User)
        .options(
            selectinload(User.keywords),
            selectinload(User.source_preferences),
        )
        .where(User.telegram_user_id == uid)
    )
    user = result.scalar_one_or_none()
    if user is None:
        await message.answer("Please use /start first.")
        return
    if not user.keywords:
        await message.answer("Add at least one keyword with /add first.")
        return

    wait_msg = await message.answer(
        "Fetching current listings… This may take up to a minute."
    )
    settings = get_settings()
    try:
        all_jobs = await fetch_all_jobs(settings, get_app_session_factory())
    except Exception:
        logger.exception("cmd_jobs: fetch_all_jobs failed")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer("Could not fetch jobs. Try again later.")
        return

    try:
        await wait_msg.delete()
    except Exception:
        pass

    matched = [
        j
        for j in all_jobs
        if user_accepts_source(user, j.source_site)
        and job_matches_user_keywords(j, user)
    ]
    matched.sort(key=lambda j: (j.source_site, j.title.lower()))
    if len(matched) > _MAX_JOBS_IN_REPLY:
        matched = matched[:_MAX_JOBS_IN_REPLY]

    if not matched:
        await message.answer(
            f"No jobs matched your keywords in this run "
            f"({len(all_jobs)} listings scraped)."
        )
        return

    chunks = _job_list_chunks(matched, len(all_jobs))
    for i, chunk in enumerate(chunks):
        text = chunk if i == 0 else f"(continued {i + 1}/{len(chunks)})\n\n{chunk}"
        if len(text) > 4096:
            text = text[:4090] + "…"
        await message.answer(text, disable_web_page_preview=True)


def _parse_source_on_off(args: str) -> tuple[str | None, str | None]:
    tokens = args.split()
    if len(tokens) < 2:
        return None, None
    onoff = frozenset({"on", "off"})
    if tokens[-1].lower() in onoff:
        return " ".join(tokens[:-1]).strip(), tokens[-1].lower()
    if tokens[0].lower() in onoff:
        return " ".join(tokens[1:]).strip(), tokens[0].lower()
    return None, None


@router.message(Command("sources"))
async def cmd_sources(message: Message, db_session) -> None:
    uid = message.from_user.id if message.from_user else message.chat.id
    result = await db_session.execute(
        select(User)
        .options(selectinload(User.source_preferences))
        .where(User.telegram_user_id == uid)
    )
    user = result.scalar_one_or_none()
    if user is None:
        await message.answer("Please use /start first.")
        return

    lines = []
    for key in KNOWN_SOURCES:
        on = user_accepts_source(user, key)
        lines.append(f"• {key}: {'ON' if on else 'OFF'}")
    await message.answer(
        "Sources for alerts and /jobs:\n"
        + "\n".join(lines)
        + "\n\nToggle: /source linkedin off  or  /source linkedin on"
    )


@router.message(Command("source"), F.text)
async def cmd_source(message: Message, command: CommandObject, db_session) -> None:
    raw = (command.args or "").strip()
    if not raw:
        await message.answer(
            "Usage: /source <site> on|off\n"
            "Sites: jobsearch, abb, kapital, glorri, linkedin\n"
            "Examples:\n/source linkedin off\n/source off kapital"
        )
        return

    name, state = _parse_source_on_off(raw)
    if not name or not state:
        await message.answer(
            "Could not parse. Use: /source <site> on|off\n"
            "Example: /source linkedin off"
        )
        return

    key = normalize_source_key(name)
    if key is None:
        await message.answer(
            f"Unknown site “{name}”. Use: jobsearch, abb, kapital, glorri, linkedin"
        )
        return

    uid = message.from_user.id if message.from_user else message.chat.id
    result = await db_session.execute(
        select(User).where(User.telegram_user_id == uid)
    )
    user = result.scalar_one_or_none()
    if user is None:
        await message.answer("Please use /start first.")
        return

    if state == "on":
        await db_session.execute(
            delete(UserSourcePreference).where(
                UserSourcePreference.user_id == user.id,
                UserSourcePreference.source_key == key,
            )
        )
        await message.answer(f"{key} is ON.")
        return

    pref_result = await db_session.execute(
        select(UserSourcePreference).where(
            UserSourcePreference.user_id == user.id,
            UserSourcePreference.source_key == key,
        )
    )
    pref = pref_result.scalar_one_or_none()
    if pref is None:
        db_session.add(
            UserSourcePreference(user_id=user.id, source_key=key, enabled=False)
        )
    else:
        pref.enabled = False
    await message.answer(f"{key} is OFF (no alerts or /jobs from this source).")


@router.message(Command("clear"))
async def cmd_clear(message: Message, db_session) -> None:
    uid = message.from_user.id if message.from_user else message.chat.id
    result = await db_session.execute(
        select(User).where(User.telegram_user_id == uid)
    )
    user = result.scalar_one_or_none()
    if user is None:
        await message.answer(
            "Nothing to clear. Use /start to register first."
        )
        return

    await db_session.execute(delete(Keyword).where(Keyword.user_id == user.id))
    await db_session.execute(
        delete(UserSourcePreference).where(
            UserSourcePreference.user_id == user.id
        )
    )
    await db_session.execute(
        delete(UserJobNotification).where(
            UserJobNotification.user_id == user.id
        )
    )
    await message.answer(
        "Your bot data has been cleared:\n"
        "• All keywords removed\n"
        "• Site on/off settings reset (all sources default ON)\n"
        "• Notification history cleared (you may get alerts for jobs you saw before)\n\n"
        "Telegram does not allow bots to erase the chat window — old messages "
        "stay until you delete them in Telegram.\n\n"
        "Use /add to track keywords again."
    )
