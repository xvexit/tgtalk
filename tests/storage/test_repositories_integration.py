from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from tgtwin.core.models import StoredMessage
from tgtwin.storage.db import get_sessionmaker
from tgtwin.storage.repositories import PostgresMessageRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repo_integration() -> None:
    url = os.environ.get("DATABASE_URL", "")
    sessionmaker = get_sessionmaker(url)
    async with sessionmaker() as session:
        repo = PostgresMessageRepository(session)
        now = datetime.now(UTC)
        m1 = StoredMessage(chat_id=999, message_id=1, role="them", text="a", ts=now)
        m2 = StoredMessage(chat_id=999, message_id=2, role="owner", text="b", ts=now)
        await repo.add(m1)
        await repo.add(m1)
        await repo.add(m2)
        assert await repo.exists(999, 1)
        items = await repo.last(999, 10)
        assert items[0].role == "them"
        assert items[-1].role == "owner"
        owner_ts = await repo.last_owner_ts(999)
        assert owner_ts is not None
