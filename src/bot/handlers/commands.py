from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from src.db.models import Keyword, User

router = Router(name="commands")


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
        "Commands:\n"
        "/add <keyword> — track a keyword (case-insensitive)\n"
        "/list — show your keywords\n"
        "/remove <keyword> — stop tracking a keyword"
    )


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
