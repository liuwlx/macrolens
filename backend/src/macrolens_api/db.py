from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Create the async engine lazily so schema/openapi tooling can import the app without a DB driver."""
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


class LazySessionFactory:
    def __call__(self, **kwargs: Any) -> AsyncSession:
        return get_session_factory()(**kwargs)


SessionLocal = LazySessionFactory()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_session_factory.cache_clear()
        get_engine.cache_clear()
