from __future__ import annotations

from datetime import UTC, datetime

from tgtwin.core.models import Context, IncomingMessage
from tgtwin.core.pipeline import Pipeline


class StopStep:
    async def handle(self, ctx: Context) -> None:
        ctx.stop = True
        ctx.reply = "SHOULD_NOT_CHANGE"


class AfterStep:
    async def handle(self, ctx: Context) -> None:
        ctx.reply = "CHANGED"


async def test_stop_stops_pipeline() -> None:
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=10,
        text="hi",
        from_owner=False,
        ts=datetime.now(UTC),
    )
    ctx = Context(msg=msg)
    pipeline = Pipeline([StopStep(), AfterStep()])
    result = await pipeline.run(ctx)
    assert result.reply == "SHOULD_NOT_CHANGE"
