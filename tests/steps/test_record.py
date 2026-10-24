from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tgtwin.core.models import Context, IncomingMessage
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.record import RecordStep


class Repo:
    def __init__(self):
        self.items = []
        self.exists_set = set()

    async def add(self, msg):
        key = (msg.chat_id, msg.message_id)
        if key in self.exists_set and msg.role == "owner":
            return
        self.items.append(msg)
        self.exists_set.add(key)

    async def exists(self, chat_id: int, message_id: int):
        return (chat_id, message_id) in self.exists_set

    async def last(self, chat_id: int, n: int):
        return []

    async def last_owner_ts(self, chat_id: int):
        return None


@pytest.mark.asyncio
async def test_record_echo_owner_stopped() -> None:
    repo = Repo()
    repo.exists_set.add((1, 5))
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=5,
        text="hi",
        from_owner=True,
        ts=datetime.now(UTC),
    )
    ctx = Context(msg=msg)
    res = await Pipeline([RecordStep(repo)]).run(ctx)
    assert res.stop is True


@pytest.mark.asyncio
async def test_record_roles() -> None:
    repo = Repo()
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=6,
        text="hi",
        from_owner=False,
        ts=datetime.now(UTC),
    )
    ctx = Context(msg=msg)
    await Pipeline([RecordStep(repo)]).run(ctx)
    assert repo.items[0].role == "them"
