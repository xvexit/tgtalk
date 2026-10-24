from __future__ import annotations

from datetime import datetime, timezone

from tgtwin.app import build_pipeline
from tgtwin.core.models import Action, IncomingMessage
from tgtwin.llm.fake import FakeLLMProvider


async def test_pipeline_smoke() -> None:
    llm = FakeLLMProvider(response="ok")
    pipeline = build_pipeline(llm)
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=10,
        text="привет",
        from_owner=False,
        ts=datetime.now(timezone.utc),
    )
    from tgtwin.core.models import Context

    ctx = Context(msg=msg)
    result = await pipeline.run(ctx)
    assert result.reply == "ok"
    assert result.action == Action.REPLY
