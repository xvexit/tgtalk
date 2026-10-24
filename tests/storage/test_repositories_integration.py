from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from tgtwin.core.models import StoredMessage
from tgtwin.storage.db import get_sessionmaker
from tgtwin.storage.models import Message
from tgtwin.storage.repositories import PostgresMessageRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repo_integration() -> None:
    url = os.environ.get("DATABASE_URL", "")
    sessionmaker = get_sessionmaker(url)
    repo = PostgresMessageRepository(sessionmaker)
    chat_id = 999123
    now = datetime.now(UTC)
    try:
        m1 = StoredMessage(chat_id=chat_id, message_id=1, role="them", text="a", ts=now)
        m2 = StoredMessage(chat_id=chat_id, message_id=2, role="owner", text="b", ts=now)
        await repo.add(m1)
        await repo.add(m1)
        await repo.add(m2)
        assert await repo.exists(chat_id, 1)
        items = await repo.last(chat_id, 10)
        assert items[0].role == "them"
        assert items[-1].role == "owner"
        owner_ts = await repo.last_owner_ts(chat_id)
        assert owner_ts is not None
    finally:
        async with sessionmaker() as session:
            from sqlalchemy import delete

            await session.execute(delete(Message).where(Message.chat_id == chat_id))
            await session.commit()
