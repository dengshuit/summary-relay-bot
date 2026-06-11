from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from summary_relay_bot.config import AppConfig
from summary_relay_bot.db.base import Base


@pytest.fixture
def app_config() -> AppConfig:
    return AppConfig(
        database_url="sqlite+aiosqlite:///:memory:",
    )


@pytest.fixture
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncSession:
    async with session_factory() as session:
        yield session
        await session.rollback()
