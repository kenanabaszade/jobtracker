from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import Settings
from src.db.models import Base

_app_session_factory = None


def set_app_session_factory(factory) -> None:
    global _app_session_factory
    _app_session_factory = factory


def get_app_session_factory():
    return _app_session_factory


def create_async_db_engine(settings: Settings):
    return create_async_engine(
        settings.resolved_database_url,
        echo=False,
    )


def get_session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope(session_factory) -> AsyncIterator[AsyncSession]:
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
