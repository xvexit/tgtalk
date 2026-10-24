from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def get_engine(database_url: str | None = None):
    url = database_url or os.environ.get("DATABASE_URL", "")
    return create_async_engine(url, echo=False)


def get_sessionmaker(database_url: str | None = None):
    engine = get_engine(database_url)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
