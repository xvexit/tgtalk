from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tgtwin.core.models import Context, IncomingMessage, ResolvedConfig
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.guard_takeover import GuardTakeoverStep


class DummyRepo:
    def __init__(self, ts):
        self.ts = ts

    async def last_owner_ts(self, chat_id: int):
        return self.ts


@pytest.mark.asyncio
async def test_guard_takeover_stops() -> None:
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=1,
        text="hi",
        from_owner=False,
        ts=datetime.now(UTC),
    )
    ctx = Context(msg=msg, cfg=ResolvedConfig())
    repo = DummyRepo(datetime.now(UTC) - timedelta(hours=1))
    pipeline = Pipeline([GuardTakeoverStep(repo, default_hours=3)])
    res = await pipeline.run(ctx)
    assert res.stop is True
