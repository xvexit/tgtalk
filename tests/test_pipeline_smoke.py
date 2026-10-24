from __future__ import annotations

from datetime import UTC, datetime

from tgtwin.app import build_pipeline
from tgtwin.config import Settings
from tgtwin.core.models import Action, IncomingMessage
from tgtwin.llm.fake import FakeLLMProvider


class DummyRepo:
    async def add(self, msg):
        return None

    async def exists(self, chat_id: int, message_id: int):
        return False

    async def last(self, chat_id: int, n: int):
        return []

    async def last_owner_ts(self, chat_id: int):
        return None


async def test_pipeline_smoke() -> None:
    llm = FakeLLMProvider(response="ok")
    pipeline = build_pipeline(DummyRepo(), llm, Settings())
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=10,
        text="привет",
        from_owner=False,
        ts=datetime.now(UTC),
    )
    from tgtwin.core.models import Context

    ctx = Context(msg=msg)
    result = await pipeline.run(ctx)
    assert result.reply == "ok"
    assert result.action == Action.REPLY
