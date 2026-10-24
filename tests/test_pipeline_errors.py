from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tgtwin.core.models import Action, Context, IncomingMessage
from tgtwin.core.pipeline import Pipeline


class FailingStep:
    async def handle(self, ctx: Context) -> None:
        ctx.reply = "should_be_cleared"
        raise RuntimeError("boom")


class AfterStep:
    async def handle(self, ctx: Context) -> None:
        ctx.reply = "changed"


async def test_failing_step_no_reply_and_no_exception() -> None:
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
    pipeline = Pipeline([FailingStep(), AfterStep()])
    result = await pipeline.run(ctx)
    assert result.reply is None
    assert result.action == Action.NONE
    assert result.stop is True
    assert result.meta.get("error") == "FailingStep"


async def test_stopped_by_filled_when_stop_set() -> None:
    class StopStep:
        async def handle(self, ctx: Context) -> None:
            ctx.stop = True

    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=11,
        text="hi",
        from_owner=False,
        ts=datetime.now(UTC),
    )
    ctx = Context(msg=msg)
    pipeline = Pipeline([StopStep()])
    result = await pipeline.run(ctx)
    assert result.meta.get("stopped_by") == "StopStep"


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValidationError):
        IncomingMessage(
            channel="telegram",
            connection_id="c1",
            chat_id=1,
            message_id=12,
            text="hi",
            from_owner=False,
            ts=datetime(2025, 1, 1),
        )
